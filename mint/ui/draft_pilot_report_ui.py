"""Local V2 report; reuse existing evidence and expert review views."""
import streamlit as st

from ..draft_pilot_report import review_rows
from ..i18n import tr


def render_pilot_report(result):
    rows = review_rows(result)
    with st.expander(tr("Исходные записи и причины непереноса"), expanded=False):
        if rows:
            statuses = sorted({row["disposition"] for row in rows})
            selected = st.multiselect(tr("Статусы обработки"), statuses,
                                      default=[],
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
