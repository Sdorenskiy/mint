"""Общий кэш процесса: индексы базы, BM25, глоссарий, измерения — один экземпляр на процесс."""


_PROCESS_CACHE = {"kb": {}, "bm25": {}, "glossary": {}, "cpt": {}, "meta": {}}


def _process_cache():
    """Один словарь на весь процесс Streamlit (переживает перезапуски скрипта): индексы базы,
    BM25, глоссарий, измеренное «символов на токен». Записи проверяются по времени изменения файлов."""
    return _PROCESS_CACHE


def _file_sig(*paths):
    sig = []
    for p in paths:
        try:
            s = p.stat()
            sig.append((str(p), s.st_mtime_ns, s.st_size))
        except OSError:
            sig.append((str(p), None, None))
    return tuple(sig)
