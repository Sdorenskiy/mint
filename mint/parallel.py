"""Параллельные запросы к модели (аудит): разделы документа и вопросы глубокой проверки.

Каждая задача выполняется в своём потоке с копией контекста вызывающего (язык интерфейса и правки промптов
сеанса хранятся в contextvars), а о готовности сообщается в вызывающем потоке: интерфейс Streamlit рисуется
только из своего потока.
"""

import contextvars
from concurrent.futures import ThreadPoolExecutor, as_completed


def parallel_map(fn, items, parallel=1, on_done=None):
    """[fn(x) for x in items] — до parallel одновременно; on_done(номер, результат) — по мере готовности.
    Исключение в задаче поднимается после того, как закончатся остальные."""
    items = list(items)
    results = [None] * len(items)
    workers = max(1, min(int(parallel or 1), len(items) or 1))
    if workers == 1:
        for i, x in enumerate(items):
            results[i] = fn(x)
            if on_done:
                on_done(i, results[i])
        return results
    error = None
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(contextvars.copy_context().run, fn, x): i for i, x in enumerate(items)}
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                results[i] = fut.result()
            except Exception as e:      # noqa: BLE001 — поднимем после остальных задач
                error = error or e
                continue
            if on_done:
                on_done(i, results[i])
    if error is not None:
        raise error
    return results
