"""Local V2 report; reuse existing evidence and expert review views."""
import json

import streamlit as st

from ..draft_pilot_report import diagnostic_export, review_rows
from ..i18n import tr


def render_pilot_report(result):
    rows = review_rows(result)
    export = diagnostic_export(result)
    st.subheader(tr("Результаты формирования V2"))
    st.caption(tr("Записано абзацев: {written}; исходных записей: {records}; связанных с текстом: {linked}.",
                  written=export["inserted_paragraphs"], records=export["records"],
                  linked=export["linked_records"]))
    st.caption(tr("Попыток исправления: {attempts}; успешно: {successes}.",
                  attempts=export["repair_attempts"], successes=export["repair_successes"]))
    st.caption(tr("Связь с текстом не означает полного переноса требования. Коды статусов — результаты обработки, не экспертные оценки."))
    with st.expander(tr("Исходные записи и причины непереноса"), expanded=True):
        if rows:
            statuses = sorted({row["disposition"] for row in rows})
            selected = st.multiselect(tr("Статусы обработки"), statuses,
                                      default=[s for s in statuses if s not in ("model_covered", "linked_evidence")],
                                      key="pilot_report_status")
            visible = [row for row in rows if row["disposition"] in selected]
            st.caption(tr("Отображено {n} из {total}.", n=len(visible), total=len(rows)))
            if visible:
                lookup = {row["id"]: row for row in visible}
                rid = st.selectbox(tr("Требование"), list(lookup),
                                   format_func=lambda k: f"{k} · {lookup[k]['source']} · {lookup[k]['quote'][:90]}",
                                   key="pilot_report_record")
                row = lookup[rid]
                st.text(f"{row['disposition']} · {row.get('kind', '')} · {row.get('source_role', '')}")
                st.text(f"{row['source']} › {row['section']}\n{row['quote']}")
                allocation = result.get("analysis", {}).get("allocations", {}).get(rid, {})
                if allocation:
                    st.text(f"{allocation.get('status', '')} · {allocation.get('category', '')}")
                    st.text(allocation.get("reason", ""))
                for question in result.get("derivation", {}).get("generated_questions", []):
                    if question.get("need_id") == rid:
                        st.text(question["question"])
    st.caption(tr("В диагностике нет текстов, имён файлов, названий моделей и идентификаторов источников. Проверьте файл перед передачей."))
    st.download_button(tr("Скачать обезличенную диагностику V2"),
                       json.dumps(export, ensure_ascii=False, indent=2),
                       file_name="mint_v2_diagnostics.json", mime="application/json",
                       key="pilot_diagnostic_export")
