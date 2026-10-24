"""Статистика базы знаний MINT по документам: векторы, фрагменты, объём текста, параметры нарезки.

Только читает файлы базы — ничего не меняет и никуда не отправляет.

Запуск:
    python kb_stats.py                      # база из KB_DIR (.env / окружение) или ~/knowledge_base
    python kb_stats.py ПАПКА_БАЗЫ           # конкретная база
    python kb_stats.py СТАРАЯ_БАЗА НОВАЯ    # сравнение двух копий (например, v17 и v19)

Как читать: число векторов почти пропорционально объёму текста и обратно пропорционально шагу нарезки
(child_size − child_overlap). Если объём текста у документа не изменился, а векторов стало меньше — другие
параметры нарезки. Если уменьшился и объём текста — документ иначе разобран (версия Docling, таблицы,
колонтитулы) или часть фрагментов не получила эмбеддинг при загрузке.
"""
import json
import os
import pickle
import sys
from collections import defaultdict
from pathlib import Path


def kb_dir_default():
    here = Path(__file__).resolve().parent
    for env_file in (here / ".env", Path.cwd() / ".env"):
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                s = line.strip()
                if s.startswith("KB_DIR=") and s[7:].strip().strip("'\""):
                    return Path(os.path.expanduser(s[7:].strip().strip("'\"")))
    return Path(os.path.expanduser(os.environ.get("KB_DIR") or "~/knowledge_base"))


def load_kb(path):
    path = Path(path)
    meta_p, parents_p, manifest_p = path / "child_metadata.pkl", path / "parent_store.json", path / "manifest.json"
    if not meta_p.is_file() or not parents_p.is_file():
        sys.exit(f"В {path} нет базы MINT (child_metadata.pkl и parent_store.json).")
    with open(meta_p, "rb") as f:
        meta = pickle.load(f)
    with open(parents_p, "r", encoding="utf-8") as f:
        parents = json.load(f)
    manifest = {}
    if manifest_p.is_file():
        with open(manifest_p, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    docs = defaultdict(lambda: {"vectors": 0, "parents": 0, "tables": 0, "text": 0, "table_text": 0,
                                "child_chars": 0, "child_with_text": 0})
    for m in meta:
        d = docs[m.get("source", "?")]
        d["vectors"] += 1
        if m.get("text"):
            d["child_chars"] += len(m["text"])
            d["child_with_text"] += 1
    for p in parents.values():
        d = docs[p.get("source", "?")]
        d["parents"] += 1
        if p.get("type") == "table":
            d["tables"] += 1
            d["table_text"] += len(p.get("text") or "")
        else:
            d["text"] += len(p.get("text") or "")
    params = manifest.get("documents") or {}
    return dict(docs), params, manifest, path


def fmt(n):
    return f"{n:,}".replace(",", " ")


def show(kb):
    docs, params, manifest, path = kb
    print(f"\nБаза: {path}")
    if manifest.get("mint_version"):
        print(f"Записана MINT {manifest['mint_version']}, {manifest.get('last_updated', '')}")
    print(f"{'Документ':42} {'векторы':>8} {'parent':>7} {'табл.':>6} {'текст, симв.':>13} {'таблицы, симв.':>15} "
          f"{'вект./10к симв.':>15}  нарезка")
    tot = defaultdict(int)
    for name in sorted(docs):
        d = docs[name]
        chars = d["text"] + d["table_text"]
        dens = d["vectors"] / chars * 10000 if chars else 0
        p = params.get(name)
        cut = (f"parent {p.get('parent_size')}/{p.get('parent_overlap')}, child {p.get('child_size')}/"
               f"{p.get('child_overlap')}, {p.get('indexed_at', '')}") if p else "не записана (загружен до v18)"
        print(f"{name[:42]:42} {fmt(d['vectors']):>8} {fmt(d['parents']):>7} {fmt(d['tables']):>6} "
              f"{fmt(d['text']):>13} {fmt(d['table_text']):>15} {dens:>15.1f}  {cut}")
        for k in ("vectors", "parents", "tables", "text", "table_text"):
            tot[k] += d[k]
    chars = tot["text"] + tot["table_text"]
    print(f"{'ИТОГО (' + str(len(docs)) + ' док.)':42} {fmt(tot['vectors']):>8} {fmt(tot['parents']):>7} "
          f"{fmt(tot['tables']):>6} {fmt(tot['text']):>13} {fmt(tot['table_text']):>15} "
          f"{(tot['vectors'] / chars * 10000 if chars else 0):>15.1f}")


def compare(old, new):
    od, _, _, op = old
    nd, _, _, np_ = new
    print(f"\nСравнение: {op}  →  {np_}")
    print(f"{'Документ':42} {'векторы':>17} {'текст+таблицы, симв.':>27}  вывод")
    for name in sorted(set(od) | set(nd)):
        a, b = od.get(name), nd.get(name)
        if not a or not b:
            print(f"{name[:42]:42} {'только в ' + ('новой' if b else 'старой'):>17}")
            continue
        ca, cb = a["text"] + a["table_text"], b["text"] + b["table_text"]
        rv = b["vectors"] / a["vectors"] if a["vectors"] else 0
        rc = cb / ca if ca else 0
        if abs(rc - 1) <= 0.05 and abs(rv - 1) > 0.1:
            why = "текст тот же — другая нарезка"
        elif rc < 0.95:
            why = "текста меньше — другой разбор документа или пропуски эмбеддингов"
        elif rc > 1.05:
            why = "текста больше — другой разбор документа"
        else:
            why = "без существенных изменений"
        print(f"{name[:42]:42} {fmt(a['vectors']):>7} → {fmt(b['vectors']):<7} {fmt(ca):>12} → {fmt(cb):<12}  {why}")


def main():
    try:
        from importlib.metadata import version
        print(f"Docling: {version('docling')}")
    except Exception:
        pass
    paths = sys.argv[1:] or [str(kb_dir_default())]
    kbs = [load_kb(p) for p in paths[:2]]
    for kb in kbs:
        show(kb)
    if len(kbs) == 2:
        compare(*kbs)


if __name__ == "__main__":
    main()
