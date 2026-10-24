"""База знаний: индексация, удаление, переиндексация, манифест, чтение."""

import bisect
import json
import logging
import os
import pickle
import re
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np

try:
    import fcntl          # блокировка записи в базу между процессами (Linux, macOS)
except ImportError:
    fcntl = None

from .bm25 import load_bm25_index, save_bm25_index
from .cache import _file_sig, _process_cache
from .i18n import tr
from .glossary import AUTO_GLOSSARY_FILE, Glossary, build_auto_glossary, load_manual_glossary
from .parsing import DocumentUnreadable, parse_document, structure_note
from .services import get_query_embedding, get_query_embeddings_batch
from .text import atomic_write_json, clean_table_markdown, split_table_markdown, split_with_overlap_pos
from .version import MINT_VERSION

logger = logging.getLogger("MINT")


KB_PARENTS = "parent_store.json"

KB_FAISS = "child_index.faiss"

KB_META = "child_metadata.pkl"

KB_BM25 = "bm25_index.pkl"

KB_MANIFEST = "manifest.json"

KB_SOURCES_DIR = "sources"        # оригиналы документов — для переиндексации после смены моделей

CHUNK_PARAM_KEYS = ("parent_size", "parent_overlap", "child_size", "child_overlap")


def read_faiss(path):
    """Индекс FAISS читается через Python: faiss.read_index на Windows не открывает путь с кириллицей
    (C:\\Users\\Иванов\\...). Формат файла тот же, что у faiss.write_index."""
    data = Path(path).read_bytes()
    if hasattr(faiss, "deserialize_index"):
        return faiss.deserialize_index(np.frombuffer(bytearray(data), dtype="uint8"))
    return faiss.read_index(str(path))


def write_faiss(index, path):
    if hasattr(faiss, "serialize_index"):
        Path(path).write_bytes(faiss.serialize_index(index).tobytes())
    else:
        faiss.write_index(index, str(path))


def kb_file(cfg, name) -> Path:
    cfg.kb_path.mkdir(parents=True, exist_ok=True)
    return cfg.kb_path / name


def source_path(cfg, filename) -> Path:
    return kb_file(cfg, KB_SOURCES_DIR) / os.path.basename(filename)


@contextmanager
def kb_write_lock(cfg):
    """Блокировка базы на время чтения-изменения-записи: два одновременных изменения (загрузка, удаление)
    не затирают друг друга. Внутри процесса — threading.RLock (сеансы Streamlit — потоки одного процесса),
    между процессами — fcntl.flock (Linux, macOS). Повторный вход в том же потоке разрешён."""
    locks = _process_cache().setdefault("locks", {})
    entry = locks.setdefault(str(cfg.kb_path), {"lock": threading.RLock(), "depth": 0, "file": None})
    with entry["lock"]:
        entry["depth"] += 1
        try:
            if entry["depth"] == 1 and fcntl is not None:
                f = open(kb_file(cfg, ".write.lock"), "w")
                fcntl.flock(f, fcntl.LOCK_EX)
                entry["file"] = f
            yield
        finally:
            entry["depth"] -= 1
            if entry["depth"] == 0 and entry["file"] is not None:
                try:
                    fcntl.flock(entry["file"], fcntl.LOCK_UN)
                finally:
                    entry["file"].close()
                    entry["file"] = None


def l2_normalize(mat):
    """Нормирует строки матрицы: для нормированных векторов порядок по L2 совпадает с порядком по косинусу."""
    mat = np.asarray(mat, dtype="float32")
    if mat.ndim == 1:
        mat = mat[None, :]
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def index_vectors(index, ids=None):
    """Векторы из FAISS-индекса (все или по номерам)."""
    if ids is None:
        n = index.ntotal
        if n == 0:
            return np.zeros((0, index.d), dtype="float32")
        try:
            return np.asarray(index.reconstruct_n(0, n), dtype="float32")
        except Exception:
            ids = range(n)
    ids = list(ids)
    if not ids:
        return np.zeros((0, index.d), dtype="float32")
    return np.array([index.reconstruct(int(i)) for i in ids], dtype="float32")


def normalized_index(index):
    """Если векторы базы не нормированы (так отдают некоторые сервисы эмбеддингов), возвращает нормированную
    копию индекса в памяти: поиск идёт по косинусу, как задумано моделью. Файл на диске не меняется."""
    n = index.ntotal
    if n == 0:
        return index, False
    try:
        sample = np.asarray(index.reconstruct_n(0, min(n, 256)), dtype="float32")
    except Exception:
        sample = index_vectors(index, range(min(n, 256)))
    if np.all(np.abs(np.linalg.norm(sample, axis=1) - 1.0) < 1e-3):
        return index, False
    fixed = faiss.IndexFlatL2(index.d)
    fixed.add(l2_normalize(index_vectors(index)))
    return fixed, True


@dataclass
class KBSnapshot:
    parent_store: dict
    metadata: list
    index: object
    order: dict = None     # parent_id → номер в базе (см. parent_order)


def parent_order(snap):
    """Номер каждого parent-фрагмента в базе. Фрагменты документа записываются подряд и в порядке текста
    (index_parsed_document), поэтому соседние номера одного документа — соседние места в тексте."""
    if snap.order is None:
        snap.order = {p: i for i, p in enumerate(snap.parent_store)}
    return snap.order


def load_kb_snapshot(cfg):
    """Индексы базы, прочитанные с диска один раз и закэшированные до следующего изменения файлов."""
    fp, pp, mp = kb_file(cfg, KB_FAISS), kb_file(cfg, KB_PARENTS), kb_file(cfg, KB_META)
    if not (fp.exists() and pp.exists() and mp.exists()):
        return None
    cache = _process_cache()["kb"]
    sig = _file_sig(fp, pp, mp)
    hit = cache.get(str(cfg.kb_path))
    if hit and hit[0] == sig:
        return hit[1]
    with kb_write_lock(cfg):   # коротко: чтобы не прочитать файлы посреди записи
        if not (fp.exists() and pp.exists() and mp.exists()):
            return None
        sig = _file_sig(fp, pp, mp)
        with open(pp, "r", encoding="utf-8") as f:
            parent_store = json.load(f)
        with open(mp, "rb") as f:
            metadata = pickle.load(f)
        index = read_faiss(fp)
    index, fixed = normalized_index(index)
    if fixed:
        logger.info("📐 Векторы базы не нормированы — нормирую в памяти (поиск по косинусу). "
                    "Переиндексация не нужна.")
    snap = KBSnapshot(parent_store, metadata, index)
    cache[str(cfg.kb_path)] = (sig, snap)
    return snap


def load_kb_metadata(cfg):
    mp = kb_file(cfg, KB_META)
    if not mp.exists():
        return []
    cache = _process_cache()["meta"]
    sig = _file_sig(mp)
    hit = cache.get(str(mp))
    if hit and hit[0] == sig:
        return hit[1]
    try:
        with open(mp, "rb") as f:
            meta = pickle.load(f)
    except Exception:
        meta = []
    cache[str(mp)] = (sig, meta)
    return meta


def load_bm25_for(cfg, parent_store):
    """BM25-индекс, согласованный с текущим parent_store; при расхождении или старом формате — пересборка."""
    path = kb_file(cfg, KB_BM25)
    cache = _process_cache()["bm25"]
    sig = _file_sig(path)
    hit = cache.get(str(path))
    if hit and hit[0] == sig:
        engine, ids = hit[1]
    else:
        engine, ids = load_bm25_index(path)
        cache[str(path)] = (sig, (engine, ids))
    if engine is None or set(ids) != set(parent_store):
        with kb_write_lock(cfg):
            save_bm25_index(parent_store, path)
        engine, ids = load_bm25_index(path)
        cache[str(path)] = (_file_sig(path), (engine, ids))
    return engine, ids


def read_manifest(cfg):
    p = kb_file(cfg, KB_MANIFEST)
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _read_parent_store(cfg):
    pp = kb_file(cfg, KB_PARENTS)
    if not pp.exists():
        return {}
    with open(pp, "r", encoding="utf-8") as f:
        return json.load(f)


def _commit_kb(cfg, index, metadata, parent_store, doc_updates=None, removed_docs=()):
    """Атомарная запись базы: всё пишется во временную папку и подменяется через os.replace."""
    kbp = cfg.kb_path
    kbp.mkdir(parents=True, exist_ok=True)
    docs = dict(read_manifest(cfg).get("documents") or {})
    for d in removed_docs:
        docs.pop(d, None)
    docs.update(doc_updates or {})
    has_index = index is not None and index.ntotal > 0

    with tempfile.TemporaryDirectory(dir=str(kbp), prefix=".tmp_") as tmp:
        tmp = Path(tmp)
        if has_index:
            write_faiss(index, tmp / KB_FAISS)
        with open(tmp / KB_META, "wb") as f:
            pickle.dump(metadata, f)
        with open(tmp / KB_PARENTS, "w", encoding="utf-8") as f:
            json.dump(parent_store, f, ensure_ascii=False, indent=2)
        manifest = {
            "manifest_version": "2",
            "mint_version": MINT_VERSION,
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_vectors": index.ntotal if has_index else 0,
            "embed_dim": index.d if has_index else None,
            "parent_chunks_count": len(parent_store),
            "documents": docs,
        }
        with open(tmp / KB_MANIFEST, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        if has_index:
            os.replace(tmp / KB_FAISS, kbp / KB_FAISS)
        elif (kbp / KB_FAISS).exists():
            (kbp / KB_FAISS).unlink()
        os.replace(tmp / KB_META, kbp / KB_META)
        os.replace(tmp / KB_PARENTS, kbp / KB_PARENTS)
        os.replace(tmp / KB_MANIFEST, kbp / KB_MANIFEST)

    save_bm25_index(parent_store, kbp / KB_BM25)
    rebuild_auto_glossary(parent_store, cfg)


def build_parent_chunks(units, tables, pages_real, filename, cfg):
    """Parent/child-фрагменты документа: текст одним потоком с заголовками + таблицы по группам строк."""
    parent_size = max(200, int(cfg.parent_size))
    child_size = max(50, min(int(cfg.child_size), parent_size))
    parent_overlap = max(0, min(int(cfg.parent_overlap), parent_size - 1))
    child_overlap = max(0, min(int(cfg.child_overlap), child_size - 1))

    # Текст одним потоком; заголовки остаются в нём строками «## Заголовок»
    stream_parts, marks, pos = [], [], 0
    for u in units:
        line = ("#" * min(max(u["level"], 1), 6) + " " + u["text"]) if u["level"] else u["text"]
        marks.append((pos, u["path"], u["page"]))
        stream_parts.append(line)
        pos += len(line) + 2
    stream = "\n\n".join(stream_parts)
    mark_starts = [m[0] for m in marks]

    def _mark_at(offset):
        if not marks:
            return (0, "", None)
        return marks[max(0, bisect.bisect_right(mark_starts, offset) - 1)]

    packed = []  # [(parent_dict, [(child_text, child_heading_path), ...])]
    for ps, _pe, ptext in split_with_overlap_pos(stream, parent_size, parent_overlap):
        _, ppath, ppage = _mark_at(ps)
        kids = []
        for cs, _ce, ctext in split_with_overlap_pos(ptext, child_size, child_overlap):
            _, cpath, _cpage = _mark_at(ps + cs)
            kids.append((ctext, cpath))
        if not kids:
            kids = [(ptext, ppath)]
        packed.append((
            {"text": ptext, "source": filename, "section": "body", "type": "paragraph",
             "page": ppage or 1, "heading_path": ppath, "page_reliable": pages_real},
            kids,
        ))

    # Таблицы: режем по группам строк, шапка колонок повторяется, заголовок таблицы — в каждой части
    for t_idx, t in enumerate(tables):
        try:
            clean_md = clean_table_markdown(t["md"])
            if not clean_md:
                continue
            title = f"Таблица №{t_idx + 1}" + (f". {t['caption']}" if t.get("caption") else "")
            parts = split_table_markdown(clean_md, parent_size)
            for part_no, part in enumerate(parts, 1):
                section = title + (f" (часть {part_no}/{len(parts)})" if len(parts) > 1 else "")
                kids = [(f"{title}\n{kid}", t["path"]) for kid in split_table_markdown(part, child_size)]
                packed.append((
                    {"text": f"{title}\n{part}", "source": filename, "section": section, "type": "table",
                     "page": t["page"] or 1, "heading_path": t["path"], "page_reliable": pages_real},
                    kids,
                ))
        except Exception as table_err:
            logger.warning(f"⚠️ Таблица №{t_idx + 1} пропущена: {str(table_err)[:120]}")
    return packed


def index_parsed_document(filename, units, tables, pages_real, structured, cfg, info=None):
    """Индексирует разобранный документ (замена прежней версии файла с тем же именем).
    Эмбеддинги считаются без блокировки базы; слияние с базой и запись — под блокировкой.
    info — как разобран документ (parsing.parse_document): формат и источник структуры пишутся в манифест."""
    n_headings = sum(1 for u in units if u["level"])
    packed = build_parent_chunks(units, tables, pages_real, filename, cfg)

    new_parents, embed_texts, child_metadatas = {}, [], []
    for parent, kids in packed:
        parent_id = str(uuid.uuid4())
        new_parents[parent_id] = parent
        for kid_text, kid_path in kids:
            # путь заголовков — только во входе эмбеддинга (контекстный заголовок фрагмента)
            body = f"{kid_path}\n{kid_text}" if kid_path else kid_text
            embed_texts.append(f"{cfg.embed_doc_prefix}{body}")
            # текст child хранится, чтобы реранкер получал именно найденный фрагмент
            child_metadatas.append({"parent_id": parent_id, "source": filename, "page": parent["page"],
                                    "text": kid_text})

    # Эмбеддинги: одна повторная попытка для пропусков и честный счётчик
    batch_vectors = get_query_embeddings_batch(embed_texts, cfg)
    retry_idx = [i for i, v in enumerate(batch_vectors) if v is None]
    if retry_idx:
        time.sleep(1.0)
        for i in retry_idx:
            vec = get_query_embedding(embed_texts[i], cfg)
            if vec is not None:
                batch_vectors[i] = vec
    n_total = len(embed_texts)
    n_skipped = sum(1 for v in batch_vectors if v is None)
    if n_skipped:
        logger.warning(f"⚠️ '{filename}': без эмбеддинга осталось {n_skipped} из {n_total} чанков.")

    vectors, valid_metadata = [], []
    for idx, vec in enumerate(batch_vectors):
        if vec is not None:
            vectors.append(vec)
            valid_metadata.append(child_metadatas[idx])
    if not vectors:
        return False, tr("Не удалось сгенерировать векторы через сервис эмбеддингов.")

    embeddings_np = l2_normalize(np.array(vectors).astype("float32"))
    dim = int(embeddings_np.shape[1])

    with kb_write_lock(cfg):
        parent_store = _read_parent_store(cfg)
        for k in [k for k, v in parent_store.items() if v.get("source") == filename]:
            del parent_store[k]
        parent_store.update(new_parents)

        fp, mp = kb_file(cfg, KB_FAISS), kb_file(cfg, KB_META)
        if fp.exists() and mp.exists():
            with open(mp, "rb") as f:
                existing_metadata = pickle.load(f)
            old_index = read_faiss(fp)
            keep = [i for i, m in enumerate(existing_metadata) if m["source"] != filename]
            if keep and old_index.d != dim:
                return False, (
                    tr("Размерность векторов текущей модели эмбеддингов ({dim}) не совпадает с базой ({d}): база "
                       "построена другой моделью. Переиндексируйте базу (кнопка в списке документов) или верните "
                       "прежнюю EMBED_MODEL.", dim=dim, d=old_index.d)
                )
            index = faiss.IndexFlatL2(dim)
            if keep:
                index.add(l2_normalize(index_vectors(old_index, keep)))
            metadata_to_save = [existing_metadata[i] for i in keep]
        else:
            index = faiss.IndexFlatL2(dim)
            metadata_to_save = []
        index.add(embeddings_np)
        metadata_to_save.extend(valid_metadata)

        doc_params = {
            "embed_model": cfg.embed_model, "embed_dim": dim, "embed_doc_prefix": cfg.embed_doc_prefix,
            **{k: int(getattr(cfg, k)) for k in CHUNK_PARAM_KEYS},
            "indexed_at": time.strftime("%Y-%m-%d %H:%M:%S"), "mint_version": MINT_VERSION,
            **({"format": info.get("format"), "structure": info.get("structure")} if info else {}),
        }
        _commit_kb(cfg, index, metadata_to_save, parent_store, doc_updates={filename: doc_params})

    msg = tr("Успешно добавлено {v} векторов.", v=embeddings_np.shape[0])
    if info and info.get("format") != "docx":
        msg += " " + tr("Заголовков: {n}.", n=n_headings) + " " + structure_note(info)
    elif not structured:
        msg += tr(" Структура документа не распознана — заголовки не использованы (плоский режим).")
    elif n_headings == 0:
        msg += tr(" Заголовки в документе не найдены (нет стилей «Заголовок»?) — привязка к разделам недоступна.")
    else:
        msg += tr(" Распознано заголовков: {n_headings}.", n_headings=n_headings)
    if n_skipped:
        msg += (tr(" ⚠️ Пропущено {n_skipped} из {n_total} чанков: не удалось получить эмбеддинг (по ним возможен "
                   "только поиск BM25 через parent).", n_skipped=n_skipped, n_total=n_total))
    return True, msg


def process_and_add_to_kb(filename, data: bytes, cfg, store_source=True):
    """Разбор документа (.docx — Docling, .pdf, .md, .txt — parsing.parse_document) и индексация. Оригинал
    сохраняется для будущей переиндексации."""
    logger.info(f"💾 ТРАНЗАКЦИЯ: Upsert для файла '{filename}'")
    try:
        try:
            parsed = parse_document(filename, data)
        except DocumentUnreadable as e:
            logger.warning(f"Документ '{filename}' не проиндексирован: {e}")
            return False, "❌ " + str(e)
        if not parsed["units"] and not parsed["tables"]:
            return False, tr("❌ В документе не найден текст.")
        ok, msg = index_parsed_document(filename, parsed["units"], parsed["tables"], parsed["pages_real"],
                                        parsed["structured"], cfg, info=parsed["info"])
        if ok and store_source:
            with kb_write_lock(cfg):
                sp = source_path(cfg, filename)
                sp.parent.mkdir(parents=True, exist_ok=True)
                sp.write_bytes(data)
        return ok, msg
    except Exception as tx_error:
        logger.exception(f"Ошибка индексации '{filename}'")
        return False, tr("❌ Ошибка транзакции: {v}", v=str(tx_error))


def delete_document_from_kb(target_filename, cfg):
    with kb_write_lock(cfg):
        fp, mp = kb_file(cfg, KB_FAISS), kb_file(cfg, KB_META)
        if not (fp.exists() and mp.exists()):
            return False
        parent_store = _read_parent_store(cfg)
        for k in [k for k, v in parent_store.items() if v.get("source") == target_filename]:
            del parent_store[k]

        with open(mp, "rb") as f:
            existing_metadata = pickle.load(f)
        old_index = read_faiss(fp)
        keep = [i for i, m in enumerate(existing_metadata) if m["source"] != target_filename]
        if keep:
            index = faiss.IndexFlatL2(old_index.d)
            index.add(l2_normalize(index_vectors(old_index, keep)))
        else:
            index = None
        _commit_kb(cfg, index, [existing_metadata[i] for i in keep], parent_store, removed_docs={target_filename})
        sp = source_path(cfg, target_filename)
        if sp.exists():
            sp.unlink()
    return True


def list_kb_documents(cfg):
    meta = load_kb_metadata(cfg)
    return sorted({m["source"] for m in meta}), len(meta)


def kb_document_status(cfg):
    """Документы базы и расхождения с текущими настройками (модель эмбеддингов, нарезка)."""
    docs, n_vectors = list_kb_documents(cfg)
    manifest_docs = read_manifest(cfg).get("documents") or {}
    rows = []
    for d in docs:
        p = manifest_docs.get(d)
        issues = []
        if p is None:
            issues.append(("info", tr("параметры индексации не записаны (документ загружен до v18)")))
        else:
            if p.get("embed_model") != cfg.embed_model or (p.get("embed_doc_prefix") or "") != cfg.embed_doc_prefix:
                issues.append(("error", tr("проиндексирован моделью эмбеддингов «{v}», сейчас — «{embed_model}»: векторный поиск по нему "
                                           "не работает", v=p.get('embed_model'), embed_model=cfg.embed_model)))
            diff = [k for k in CHUNK_PARAM_KEYS if p.get(k) != int(getattr(cfg, k))]
            if diff:
                issues.append(("info", tr("нарезан с другими параметрами: ") +
                               ", ".join(f"{k} {p.get(k)} → {int(getattr(cfg, k))}" for k in diff)))
        rows.append({"name": d, "issues": issues, "has_source": source_path(cfg, d).exists()})
    return rows, n_vectors


def _clear_kb_index(cfg):
    """Удаляет индексы базы (оригиналы документов в sources/ остаются)."""
    with kb_write_lock(cfg):
        for name in (KB_FAISS, KB_META, KB_PARENTS, KB_BM25, KB_MANIFEST, AUTO_GLOSSARY_FILE):
            p = kb_file(cfg, name)
            if p.exists():
                p.unlink()


def reindex_documents(cfg, progress=None):
    """Переиндексирует документы с сохранёнными оригиналами по текущим настройкам.
    Если сменилась размерность векторов (другая модель эмбеддингов) — база строится заново:
    документы без оригинала при этом удаляются (их нужно загрузить повторно)."""
    rows, _ = kb_document_status(cfg)
    with_src = [r["name"] for r in rows if r["has_source"]]
    probe = get_query_embedding("проверка размерности", cfg)
    if probe is None:
        return [("—", False, tr("Сервис эмбеддингов недоступен — переиндексация не начата."))]
    snap = load_kb_snapshot(cfg)
    if snap is not None and len(probe) != snap.index.d:
        logger.warning(f"Размерность {snap.index.d} → {len(probe)}: база строится заново")
        _clear_kb_index(cfg)
    results = []
    for i, name in enumerate(with_src):
        ok, msg = process_and_add_to_kb(name, source_path(cfg, name).read_bytes(), cfg, store_source=False)
        results.append((name, ok, msg))
        if progress:
            progress((i + 1) / max(1, len(with_src)), name)
    return results


def kb_parent_lengths(cfg):
    snap = load_kb_snapshot(cfg)
    if snap is None:
        return []
    return sorted(len(v.get("text") or "") for v in snap.parent_store.values())


_CYR = re.compile(r"[а-яё]")
_LAT = re.compile(r"[a-z]")


def kb_language(cfg, sample_parents=400, chars_per_parent=2000):
    """Язык базы по буквам в тексте фрагментов (выборка по всей базе): ('ru' | 'en' | 'mixed', доля кириллицы)
    или (None, 0.0), если база пуста. Русские документы с английскими терминами и аббревиатурами остаются 'ru'."""
    snap = load_kb_snapshot(cfg)
    if snap is None or not snap.parent_store:
        return None, 0.0
    values = list(snap.parent_store.values())
    step = max(1, len(values) // sample_parents)
    cyr = lat = 0
    for v in values[::step]:
        text = (v.get("text") or "")[:chars_per_parent].lower()
        cyr += len(_CYR.findall(text))
        lat += len(_LAT.findall(text))
    if not cyr + lat:
        return None, 0.0
    share = cyr / (cyr + lat)
    return ("ru" if share >= 0.8 else "en" if share <= 0.2 else "mixed"), round(share, 2)


def kb_default_top_k(cfg):
    n_chunks = len(load_kb_metadata(cfg))
    return 4 if n_chunks <= 300 else 5


def rebuild_auto_glossary(parent_store, cfg):
    data = build_auto_glossary(parent_store)
    atomic_write_json(kb_file(cfg, AUTO_GLOSSARY_FILE), data)
    logger.info(f"📘 Автоглоссарий: {len(data)} сокращений")
    return len(data)


def load_glossary(cfg) -> Glossary:
    """Глоссарий: найденное в документах + свой glossary.json (свои записи важнее)."""
    manual_path = cfg.glossary_file
    auto_path = kb_file(cfg, AUTO_GLOSSARY_FILE)
    parents_path = kb_file(cfg, KB_PARENTS)
    if cfg.glossary_auto and not auto_path.exists() and parents_path.exists():
        try:  # база создана до v18 — собираем сокращения один раз
            rebuild_auto_glossary(_read_parent_store(cfg), cfg)
        except Exception as e:
            logger.warning(f"Автоглоссарий не собран: {str(e)[:120]}")

    key = (_file_sig(manual_path, auto_path), cfg.glossary_auto)
    cache = _process_cache()["glossary"]
    hit = cache.get(str(cfg.kb_path))
    if hit and hit[0] == key:
        return hit[1]
    manual = load_manual_glossary(manual_path)
    auto = {}
    if cfg.glossary_auto and auto_path.exists():
        try:
            with open(auto_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            auto = {a: (v.get("full") if isinstance(v, dict) else str(v)) for a, v in raw.items() if v}
            auto = {a: f for a, f in auto.items() if f}
        except Exception as e:
            logger.warning(f"auto_glossary.json не прочитан: {str(e)[:120]}")
    gl = Glossary(manual, auto)
    cache[str(cfg.kb_path)] = (key, gl)
    return gl
