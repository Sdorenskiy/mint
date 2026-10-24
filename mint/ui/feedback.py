"""Интерфейс: оценка 👍/👎 с комментарием под результатом и сводка отзывов в боковой панели."""

import streamlit as st

from ..feedback import RATINGS, feedback_path, feedback_summary, read_feedback, record_feedback
from ..i18n import N_, tr

KIND_TITLES = {"chat": N_("ответы чата"), "audit": N_("аудит"), "review": N_("контроль исправлений")}


def render_feedback(cfg, kind, item_id, context, subject=""):
    """Кнопки 👍/👎 под ответом; после оценки — необязательный комментарий.
    context — словарь или функция без аргументов, которая его вернёт (вызывается только при оценке)."""
    state = st.session_state.setdefault("mint_feedback", {})
    key = f"{kind}_{item_id}"
    done = state.get(key)
    if done is None:
        c1, c2, _ = st.columns([1, 1, 10])
        with c1:
            up = st.button("👍", key=f"fb_up_{key}", help=tr("Полезно, по делу"))
        with c2:
            down = st.button("👎", key=f"fb_down_{key}", help=tr("Неверно, неполно или не по делу"))
        if not (up or down):
            return
        rating = "up" if up else "down"
        ctx = context() if callable(context) else dict(context or {})
        ok = record_feedback(cfg, kind, rating, item_id, {"subject": subject, **ctx})
        done = state[key] = {"rating": rating, "ok": ok, "comment_sent": False}
    if not done["ok"]:
        st.caption(tr("⚠️ Оценку не удалось записать в {v} — подробности в журнале MINT.", v=feedback_path(cfg)))
        return
    mark = RATINGS[done["rating"]]
    if done["comment_sent"]:
        st.caption(tr("{mark} Спасибо! Оценка и комментарий записаны.", mark=mark))
        return
    question = (tr("Что не так: ошибка, пропуск, лишнее, не тот источник?") if done["rating"] == "down"
                else tr("Что особенно помогло?"))
    comment = st.text_input(tr("{mark} Оценка записана. {question} (необязательно)", mark=mark, question=question), key=f"fb_text_{key}",
                            placeholder=tr("Комментарий для разработчика"))
    if st.button(tr("Отправить комментарий"), key=f"fb_send_{key}"):
        if comment.strip():
            done["ok"] = record_feedback(cfg, kind, "comment", item_id, {"subject": subject}, comment)
            done["comment_sent"] = True
            st.rerun()
        else:
            st.caption(tr("Комментарий пустой — нечего отправлять."))


def render_feedback_panel(cfg):
    """Боковая панель: сколько оценок записано и кнопка, чтобы переслать файл разработчику."""
    rows = read_feedback(cfg)
    summary, comments = feedback_summary(rows)
    total = sum(sum(v.values()) for v in summary.values())
    with st.expander(tr("💬 Отзывы: {total}", total=total), expanded=False):
        st.caption(tr("Оценивайте результаты кнопками 👍/👎 под ответами, заключением аудита и матрицей контроля — это "
                      "главный источник улучшений MINT."))
        if not rows:
            st.caption(tr("Оценок пока нет. Они будут записываться в {v}.", v=feedback_path(cfg)))
            return
        for kind, counts in summary.items():
            st.write(f"{tr(KIND_TITLES.get(kind, kind))}: 👍 {counts.get('up', 0)} · 👎 {counts.get('down', 0)}")
        if comments:
            st.caption(tr("Комментариев: {comments}", comments=comments))
        st.download_button(
            tr("⬇️ Скачать отзывы (feedback.jsonl)"), data=feedback_path(cfg).read_bytes(), file_name="feedback.jsonl",
            mime="application/json", key="feedback_download",
            help=tr("Перешлите файл разработчику MINT. В нём вопросы, ответы и цитаты из ваших документов — "
                    "отправляйте только туда, куда можно передавать эти документы."),
        )
        st.caption(tr("Файл: {v}", v=feedback_path(cfg)))
