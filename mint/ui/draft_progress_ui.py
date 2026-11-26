"""One progress renderer for registry-only, Word pilot and legacy drafting."""
import time

import streamlit as st

from ..draft_progress import StageProgress
from ..i18n import N_, tr

_STAGES = {
    "source_read": N_("Чтение оригиналов оснований"),
    "target_section_map": N_("Классификация разделов оснований"),
    "target_profile_search": N_("Поиск сведений о системе"),
    "target_profile": N_("Выделение функций и сведений"),
    "target_function_discovery": N_("Определение функций по исходным требованиям"),
    "reference_map": N_("Разрешение перекрёстных ссылок"),
    "reference_context": N_("Сбор связанных фрагментов"),
    "target_dossier": N_("Целевой поиск характеристик функций"),
    "target_characteristic_review": N_("Проверка характеристик функций"),
    "extract": N_("Разбор оснований"),
    "registry_type": N_("Типизация исходных сведений"),
    "target_allocation": N_("Распределение ответственности"),
    "target_verify": N_("Проверка ответственности и изменений"),
    "target_summary": N_("Сводные формулировки требований"),
    "target_derivation": N_("Детализация требований"),
    "requirement_assessment": N_("Проверка обоснованности"),
    "target_coverage": N_("Проверка полноты функций"),
    "layout": N_("Разбор шаблона"),
    "table": N_("Подготовка таблиц"),
    "scope": N_("Применимость требований"),
    "section_plan": N_("План разделов документа"),
    "fill": N_("Заполнение и сверка с вики"),
    "fixed": N_("Сверка требований шаблона"),
    "function_group": N_("Группировка функций"),
    "function_allocation": N_("Распределение ответственности"),
    "requirement_derivation": N_("Детализация требований"),
    "pilot_coverage": N_("Проверка полноты раздела"),
    "pilot_repair": N_("Исправление отклонённых требований"),
    "word_write": N_("Запись Word"),
}


def render_progress(status):
    tracker = StageProgress(time.monotonic)
    placeholder = st.empty()

    def update(event, value):
        if not tracker.update(event, value):
            return
        lines = []
        rows = tracker.snapshot()
        for row in rows:
            name = tr(_STAGES.get(row["stage"], row["stage"]))
            total, done = row["total"], row["done"]
            count = f"{done} / {total}" if total is not None else str(done)
            elapsed = tr("Прошло {seconds} с", seconds=round(row["elapsed"]))
            line = f"{name} · {count} · {elapsed}"
            if total:
                line += f" · {min(100, round(done * 100 / total))}%"
            if row["eta"] is not None:
                line += " · " + tr("Осталось примерно {minutes} мин", minutes=max(1, round(row["eta"] / 60)))
            if row["stage"] == "extract":
                if tracker.cached:
                    line += " · " + tr("Из кэша") + f": {tracker.cached}"
                if tracker.failed:
                    line += " · " + tr("Фрагментов с ошибками: {n}", n=tracker.failed)
            lines.append(line)
        if lines:
            placeholder.text("\n".join(lines))
            active = next((r for r in rows if r["stage"] == tracker.active), None)
            if active:
                label = tr(_STAGES.get(active["stage"], active["stage"]))
                count = f"{active['done']} / {active['total']}" if active["total"] is not None else str(active["done"])
                status.update(label=f"{label} · {count}")

    return update
