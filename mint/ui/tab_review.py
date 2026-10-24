"""Интерфейс: вкладка «Контроль исправлений»."""

import streamlit as st

from ..feedback import new_feedback_id
from ..i18n import tr
from ..parsing import SUPPORTED_FORMATS, DocumentUnreadable, document_to_markdown
from ..review import MIN_REMARK_CHARS, generate_word_matrix, verify_remarks
from .common import btn_w
from .feedback import render_feedback
from .theme import review_tally_html


def render_review_tab(cfg, gl):
    """Вкладка «Контроль исправлений»: статус замечаний в новой редакции документа."""
    st.subheader(tr("🤖 Автоматическая контр-проверка устранения замечаний"))
    st.info(tr("Вставьте список выданных замечаний и загрузите новую редакцию документа."))
    use_wiki_rag_tab3 = st.checkbox(
        tr("🧠 Использовать базу знаний при верификации"), value=True, key="tab3_wiki_rag_toggle",
        help=tr("Для каждого замечания дополнительно подтягиваются нормативные фрагменты из базы."),
    )
    remarks_input = st.text_area(
        tr("📝 Ранее выданные замечания (каждое с новой строки):"),
        placeholder=tr("Пример:\n- [КРИТИЧНЫЙ] Не указано шифрование ГОСТ\n- [СРЕДНИЙ] Завышен SLA."),
        key="tab3_remarks_area", height=150,
        help=tr("Каждое замечание с новой строки; строки короче {n} символов игнорируются.", n=MIN_REMARK_CHARS),
    )
    new_version_file = st.file_uploader(
        tr("Загрузить новую редакцию документа (.docx, .pdf, .md, .txt)"), type=list(SUPPORTED_FORMATS),
        key="tab3_v2_uploader",
        help=tr("Новая редакция документа, в которой нужно проверить устранение замечаний."),
    )

    if new_version_file is not None and remarks_input.strip():
        st.success(tr("Документ '{name}' загружен.", name=new_version_file.name))
        if st.button(tr("🔍 Запустить контр-проверку исправления дефектов"), key="tab3_run_btn", **btn_w):
            with st.status(tr("Сличение редакций..."), expanded=True) as status:
                try:
                    md_text_v2 = document_to_markdown(new_version_file.name, bytes(new_version_file.getbuffer()))
                except DocumentUnreadable as e:
                    status.update(label=str(e), state="error")
                    st.error(str(e))
                    return
                ui = {}

                def on_progress(event, **d):
                    if event == "sections":
                        st.write(tr("📜 Новая редакция разбита на {n_sections_v2} разделов.", n_sections_v2=d["n"]))
                    elif event == "index" and not d["dense"]:
                        st.warning(tr("⚠️ Эмбеддинги разделов недоступны — фрагменты подбираются только по словам (BM25)."))
                    elif event == "remark":
                        if "bar" not in ui:
                            ui["bar"] = st.progress(0)
                        ui["bar"].progress((d["index"] + 1) / max(1, d["total"]))

                res = verify_remarks(remarks_input, md_text_v2, cfg, use_wiki=use_wiki_rag_tab3, glossary=gl,
                                     on_progress=on_progress)
                rows = res["rows"]
                if res["unverified"]:
                    status.update(label=tr("🏁 Контр-проверка завершена, но {n_unverified} из {n_final_matrix_data} замечаний не удалось "
                                           "проверить", n_unverified=res["unverified"], n_final_matrix_data=len(rows)),
                                  state="error", expanded=True)
                else:
                    status.update(label=tr("🏁 Контр-проверка завершена!"), state="complete", expanded=False)

            st.session_state["tab3_result"] = {
                "id": new_feedback_id(), "file": new_version_file.name, "rows": rows,
                "matrix_md": res["matrix_md"], "remarks": remarks_input, "prompts": res["prompts"],
                "word": generate_word_matrix(rows, filename=tr("Матрица_{name}.docx", name=new_version_file.name)),
            }

    result = st.session_state.get("tab3_result")
    if result and new_version_file is not None and result["file"] == new_version_file.name:
        _render_review_result(cfg, result)


def _render_review_result(cfg, result):
    """Результат контр-проверки — из сеанса: не пропадает после скачивания файлов и оценки."""
    name = result["file"]
    st.markdown(tr("## 📊 Результаты проверки"))
    st.markdown(review_tally_html(result["rows"]), unsafe_allow_html=True)
    st.markdown(result["matrix_md"])
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            label=tr("📥 Скачать матрицу контроля (.md)"), data=result["matrix_md"],
            file_name=tr("Матрица_контроля_{name}.md", name=name), mime="text/markdown", key="tab3_download_md",
        )
    with c2:
        if result["word"]:
            st.download_button(
                label=tr("📥 Скачать отчёт в Word (.docx)"), data=result["word"],
                file_name=tr("Матрица_контроля_{name}.docx", name=name),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="tab3_download_docx",
            )
    st.markdown(tr("**Оцените контр-проверку:** верно ли определены статусы замечаний?"))
    render_feedback(cfg, "review", result["id"], subject=name, context=lambda: {
        "file": name, "remarks": result["remarks"], "matrix": result["matrix_md"],
        "statuses": [row["status"] for row in result["rows"]], "prompts": result.get("prompts") or "",
    })
