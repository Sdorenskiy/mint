"""[integration] Equal-dimensional model changes, legacy profiles, safe full rebuild."""
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness
import mock_server
W = harness.make_project(prefix="mint_profiles_")
srv = mock_server.start()
base = f"http://127.0.0.1:{srv.server_address[1]}/v1"
os.environ.update(EMBED_API_URL=base + "/embeddings", KB_DIR=str(W / "kb"),
                  MINT_CONFIG=str(W / "none.yaml"), LOG_DIR=str(W / "logs"), MINT_LANG="ru")
app = harness.load_mint(W, include_ui=False)
from mint import kb, search
cfg = replace(app.Settings(), kb_dir=str(W / "kb"), embed_url=base + "/embeddings", embed_model="emb-model")
check = harness.Checker()
with patch.dict(os.environ, {"EMBED_REVISION": "deployment-v2"}):
    loaded, _ = app.load_settings()
    check(loaded.embed_revision == "deployment-v2", "revision can be configured through environment")
vec = [1.0, 0.0, 0.0]
with patch.object(kb, 'get_query_embeddings_batch', side_effect=lambda texts, c: [vec for _ in texts]):
    for name in ('a.txt', 'b.txt'):
        ok, msg = kb.process_and_add_to_kb(name, b'Journal retention is three years. ' * 40, cfg)
        check(ok, f'initial document {name}', msg)
    def files():
        return {n: (cfg.kb_path / n).read_bytes() for n in
                (kb.KB_FAISS, kb.KB_META, kb.KB_PARENTS, kb.KB_MANIFEST)}
    before = files()
    for change in (dict(embed_model='other-same-dim'), dict(embed_url=base + '/other'),
                   dict(embed_doc_prefix='passage: '), dict(embed_revision='v2'), dict(embed_input_max_chars=55)):
        other = replace(cfg, **change)
        ok, _ = kb.process_and_add_to_kb('new.txt', b'new journal ' * 40, other)
        check(not ok and files() == before, f'{change}: append rejected without changing old files')
        with patch.object(search, 'get_query_embedding', side_effect=AssertionError('dense must be disabled')):
            _, sources = search.search_parent_child('journal retention', other, glossary=app.Glossary({}, {}))
        check(bool(sources) and all('dense —' in s for s in sources), 'BM25 works without dense API request')
    # Failure midway through publication rolls all index files back.
    real_replace = kb.os.replace
    fired = [False]
    def fail_publish(src, dst):
        if Path(dst) == cfg.kb_path / kb.KB_PARENTS and not fired[0]:
            fired[0] = True
            raise OSError('simulated disk error')
        return real_replace(src, dst)
    with patch.object(kb.os, 'replace', side_effect=fail_publish):
        ok, _ = kb.process_and_add_to_kb('new.txt', b'Journal ' * 50, cfg)
    check(not ok and fired[0] and files() == before, 'publication failure rolls back all live files')
    with patch.object(kb, 'get_query_embeddings_batch', side_effect=lambda texts, c: [vec] + [None] * (len(texts)-1)), \
            patch.object(kb, 'get_query_embedding', return_value=None), patch.object(kb.time, 'sleep'):
        result = kb.reindex_documents(replace(cfg, child_size=40, child_overlap=0))
    check(any(not ok for _, ok, _ in result) and files() == before, 'partial embeddings cannot publish replacement')
    snap = kb.load_kb_snapshot(cfg)
    check(kb.embeddings_compatible(replace(cfg, embed_api_key='rotated', embed_query_prefix='query: '),
                                  3, snap.metadata, snap.documents),
          'API key rotation and query instructions do not require rebuilding document vectors')
    other = replace(cfg, embed_model='other-same-dim')
    # A failure after one successful staging document must not publish the first one.
    original = kb.process_and_add_to_kb
    def fail_second(name, *args, **kwargs):
        return (False, 'simulated failure') if name == 'b.txt' else original(name, *args, **kwargs)
    with patch.object(kb, 'process_and_add_to_kb', side_effect=fail_second):
        result = kb.reindex_documents(other)
    check(any(not ok for _, ok, _ in result) and files() == before, 'failed rebuild keeps whole old base')
    sp = kb.source_path(cfg, 'b.txt'); data = sp.read_bytes(); sp.unlink()
    result = kb.reindex_documents(other)
    check(any(not ok for _, ok, _ in result) and files() == before, 'missing source keeps old base')
    recovered, message = kb.process_and_add_to_kb('b.txt', data, other)
    check(not recovered and sp.read_bytes() == data and files() == before and 'Оригинал сохранён' in message,
          'missing original can be uploaded after model change without mixing vectors')
    result = kb.reindex_documents(other)
    snap = kb.load_kb_snapshot(other)
    check(all(ok for _, ok, _ in result) and kb.embeddings_compatible(other, 3, snap.metadata, snap.documents),
          'equal-dimensional model change rebuilds all documents')
    with patch.object(search, 'get_query_embedding', return_value=vec) as request:
        search.search_parent_child('journal retention', other, glossary=app.Glossary({}, {}))
        check(request.called, 'dense restored after full rebuild; cached manifest refreshed')
    manifest = kb.read_manifest(other)
    for params in manifest['documents'].values():
        params.pop('embedding_profile', None)
    (other.kb_path / kb.KB_MANIFEST).write_text(json.dumps(manifest))
    snap = kb.load_kb_snapshot(other)
    check(not kb.embeddings_compatible(other, 3, snap.metadata, snap.documents), 'legacy profile is unknown, not assumed compatible')
    ok, _ = kb.process_and_add_to_kb('new.txt', b'Journal ' * 50, other)
    check(not ok, 'legacy vectors cannot receive a new incompatible append')
srv.shutdown()
check.finish()
