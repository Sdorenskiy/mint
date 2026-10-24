"""Инженерная схема MINT: расчёт параметров, карта настройки, бизнес-особенности, устройство функций."""
import sys

import xl
from xl import arrow, base, box, elements, needed_height, text_el, text_size, wrap

DARK, GRAY, GRAY_BG, FRAME = "#1e1e1e", "#868e96", "#f8f9fa", "#95779c"
CODE, CODE_BG = "#1971c2", "#e7f5ff"
STORE, STORE_BG = "#1e1e1e", "#fff9db"
TAG = {  # категория параметра: (цвет рамки/текста, фон, название)
    "Р": ("#e03131", "#fff5f5", "ВРУЧНУЮ"),
    "А": ("#0c8599", "#e3fafc", "АВТО"),
    "Т": ("#6741d9", "#f3f0ff", "ТЕСТ"),
    "П": ("#e8590c", "#fff4e6", "ПРОВЕРКА"),
    "У": ("#495057", "#f1f3f5", "УМОЛЧАНИЕ"),
}
W = 2400          # ширина панели
PX = 30           # внутренний отступ панели
FS = 16

frames = []


def panel_start(y, title, subtitle=None):
    text_el(PX, y + 20, title, 30, DARK)
    if subtitle:
        sub_w = wrap(subtitle, int((W - 2 * PX) / (17 * xl.CHAR_W)))
        text_el(PX, y + 64, sub_w, 17, GRAY)
        return y + 64 + text_size(sub_w, 17)[1] + 18
    return y + 76


def panel_end(y_top, y_bottom, color=FRAME):
    fr = base("rectangle", 0, y_top, W, y_bottom - y_top + 30, color, "transparent")
    frames.append(fr)
    return y_bottom + 30


def row_boxes(x, y, widths, texts, styles, gap=30, size=FS, align="left", min_h=0, text_color=None):
    """Ряд блоков одной высоты. styles — [(рамка, фон)] или одна пара для всех."""
    if isinstance(styles, tuple):
        styles = [styles] * len(texts)
    h = max([needed_height(t, w, size) for t, w in zip(texts, widths)] + [min_h]) + 8
    out, cx = [], x
    for t, w, (sc, bg) in zip(texts, widths, styles):
        out.append(box(cx, y, w, h, t, sc, bg, size=size, align=align, valign="top",
                       text_color=text_color or (DARK if sc in (STORE,) else None)))
        cx += w + gap
    return out, h


# ======================================================================== заголовок и легенда
y = 0
text_el(PX, y, "MINT — инженерная схема: устройство и настройка параметров", 40, DARK)
_sub0 = wrap("По коду MINT 20.1 и новее (пакет mint/) и eval_search.py. Для администратора: что задать при установке, "
             "что MINT рассчитает сам, что подобрать тестами на своих данных и от каких особенностей компании "
             "это зависит. Каждый факт указан в одном месте; «панель N» — где искать подробности.",
             int((W - 2 * PX) / (18 * xl.CHAR_W)))
text_el(PX, y + 58, _sub0, 18, GRAY)
y += 58 + text_size(_sub0, 18)[1] + 30
legend = [
    ("Р", "ВРУЧНУЮ — задаёт администратор: .env, config.yaml, панель"),
    ("А", "АВТО — MINT рассчитывает по моделям и базе; трогать, если есть предупреждение или так требуют тесты"),
    ("Т", "ТЕСТ — подбирается проверкой качества на своём наборе вопросов"),
    ("П", "ПРОВЕРКА — подбирается вручную на живых примерах"),
    ("У", "УМОЛЧАНИЕ — обычно не трогать"),
]
RW_ = 420
lw = (W - 2 * PX - 5 * 20 - RW_) / 5
RECYCLE = "♻ — действует на документы, загруженные после изменения; уже загруженные — переиндексация"
lh_ = max([needed_height(f"[{t}] {x_}", lw, 16) for t, x_ in legend] + [needed_height(RECYCLE, RW_, 16)]) + 4
cx = PX
for k, (tag, txt) in enumerate(legend):
    sc, bg, _ = TAG[tag]
    box(cx, y, lw, lh_, f"[{tag}] {txt}", sc, bg, size=16)
    cx += lw + 20
box(cx, y, RW_, lh_, RECYCLE, DARK, "#ffffff", size=16, dashed=True)
y += lh_ + 16
KEY_BG, KEY_SC = "#ffec99", "#f08c00"
LW2 = (W - 2 * PX - 20) / 2
_k1 = box(PX, y, LW2, 64, "◆ ОПОРНЫЙ ПАРАМЕТР — от него MINT рассчитывает другие: лимиты моделей, chars_per_token, "
                          "max_tokens, top_k и промежуточные chat_budget / llm_budget. Меняете его — меняются зависимые.",
          KEY_SC, KEY_BG, size=16, align="left", text_color=DARK)
_k1["strokeWidth"] = 4
box(PX + LW2 + 20, y, LW2, 64, "◇ ВЛИЯЕТ НА СОСЕДНИЙ — от него зависят 1–2 параметра той же группы "
                               "(parent_size → parent_overlap, audit_map_size → audit_context_max_chars …). "
                               "Зависимые перечислены в колонке «Ограничения и зависимости».",
    KEY_SC, "#fff9db", size=16, align="left", text_color=DARK)
y += 64 + 16
TOK_L = (
    "ТОКЕНЫ И СИМВОЛЫ — две единицы длины текста на этой схеме\n"
    "• [ток.] токены — так длину считают модели: токен — кусок слова (часто 2–4 буквы). В токенах заданы лимиты "
    "моделей (llm_context_tokens, embed_max_tokens, rerank_max_tokens) и длина ответа max_tokens.\n"
    "• [симв.] символы — так текст режет MINT (фрагменты, разделы документа, контекст). Все размеры фрагментов и "
    "объёмы контекста — в символах.\n"
    "• Перевод: chars(t) = t × chars_per_token × 0.85, где 0.85 (LIMIT_SAFETY) — запас 15 % на неточность "
    "оценки. Пример: 1000 ток. × 2.5 × 0.85 = 2125 симв., которые MINT позволит себе отправить."
)
TOK_R = (
    "СКОЛЬКО СИМВОЛОВ В ТОКЕНЕ (chars_per_token)\n"
    "• русский текст: 2.3–3 на современных многоязычных токенизаторах (Qwen2.5 / Qwen3, Llama 3); 1.5–2 на "
    "старых, «английских» (Llama 2, ранние Mistral)\n"
    "• английский текст: ≈ 4 (3.5–4.5);  таблицы, номера, коды: 1.5–2.5\n"
    "• 2.5 — НЕ вычисляется само: это типовое значение (FALLBACK_LIMITS), пока ничего не измерено. Вычисляется "
    "только по кнопке «Определить у сервера»: measure_chars_per_token() отправляет LLM образец на языке базы "
    "(kb_language(): русская — русский, английская — английский, смешанная или пустая — оба, берётся меньшее) и "
    "он же × 4, cpt = разница символов / разница prompt_tokens (служебные токены сокращаются). Результат "
    "живёт до перезапуска MINT — закрепить: config.yaml → models: chars_per_token.\n"
    "• одно значение берётся и для эмбеддингов, и для реранкера, хотя токенизаторы у них свои — ещё одна причина "
    "для запаса 15 %."
)
TW2 = (W - 2 * PX - 20) / 2
th2 = max(needed_height(TOK_L, TW2, 16), needed_height(TOK_R, TW2, 16)) + 6
box(PX, y, TW2, th2, TOK_L, CODE, CODE_BG, size=16, align="left", valign="top", text_color=DARK)
box(PX + TW2 + 20, y, TW2, th2, TOK_R, CODE, CODE_BG, size=16, align="left", valign="top", text_color=DARK)
y += th2 + 50

# ======================================================================== 1. расчёт параметров при запуске
p1 = y
y = panel_start(y, "1. Как MINT устанавливает параметры при запуске",
                "Каждый перезапуск страницы: main() → _base_settings() → resolve_model_limits() → resolve_settings(). "
                "Слева — откуда берутся значения, в центре — функции, которые их соединяют, справа — что чего важнее.")
SRC_W, CH_W = 700, 760
CH_X = PX + SRC_W + 60
PR_X = CH_X + CH_W + 60
PR_W = W - PX - PR_X
sources = [
    ("Р", ".env → load_settings() → _load_env_files()\nкуда подключаться: адреса и ключи API, имена моделей, папки, "
          "сертификат. Полный список — панель 3, «Подключения»."),
    ("Р", "config.yaml → load_settings()\nкак работать: лимиты моделей, поиск, аудит. Указанные параметры "
          "запоминаются (explicit_fields); подключения здесь игнорируются, неизвестные параметры — предупреждение "
          "в панели."),
    ("А", "Серверы моделей → detect_server_info()\nGET …/models → context_from_model_info(): окно LLM (max_model_len, "
          "context_length, n_ctx …), вход эмбеддингов и реранкера — если сервер сообщает; кэш 10 мин."),
    ("А", "Кнопка «Определить у сервера» → measure_chars_per_token()\nизмеряет «символов на токен» на языке "
          "базы (как — блок «Токены и символы» вверху)."),
    ("Р", "Боковая панель → st.session_state\n«Модели и лимиты», «Экспертные настройки»: изменения на время сеанса; "
          "«Сбросить изменения сеанса» возвращает как было."),
    ("А", "База знаний → kb_default_top_k()\nесли top_k не задан (0), предлагает его по числу фрагментов в базе — "
          "4 или 5 (подробно — панель 3, top_k)."),
]
src_els, sy = [], y + 44
src_z = len(elements)            # группа источников должна лежать под блоками
text_el(PX + 16, y + 10, "Откуда берутся значения", 18, DARK)
for tag, t in sources:
    sc, bg, _ = TAG[tag]
    h = needed_height(f"[{tag}] {t}", SRC_W - 32, FS) + 10
    src_els.append(box(PX + 16, sy, SRC_W - 32, h, f"[{tag}] {t}", sc, bg, size=FS, align="left", valign="top",
                       text_color=DARK))
    sy += h + 16
src_bottom = sy
src_group = base("rectangle", PX, y, SRC_W, src_bottom - y, GRAY, "#ffffff")
elements.insert(src_z, src_group)

chain_txt = [
    "resolve_model_limits() ← лимиты из источников слева\nдля каждого из 4 лимитов моделей выбирает источник по "
    "приоритету (справа); ничего нет — типовое значение (почему такие — панель 3).",
    "embed_prefix_preset(EMBED_MODEL)\nподбирает префиксы запроса и документа по имени модели эмбеддингов (таблица — "
    "панель 3, embed_query_prefix).",
    "resolve_settings() → _derive() ← параметры из источников слева\nрассчитывает 12 параметров по лимитам моделей. "
    "Правило: значение = меньшее из умолчания и потолка модели. Большое окно не раздувает фрагменты (длинный "
    "контекст добавляет шум), маленькое уменьшает их, чтобы ничего не обрезалось. Формулы — колонка «Ограничения» "
    "в панели 3, наглядно — панель 2. Итог: cfg (неизменяемый Settings) и info {value, auto, ceiling, source} → "
    "блок «MINT рассчитал».",
    "limits_warnings()\nпредупреждение в «Модели и лимиты», если значение больше потолка или модели не хватает места.",
    "ask_llm() при каждом вызове\nесли окно LLM известно (сервер, config.yaml или панель): оценивает запрос в токенах; "
    "свободно < 256 ток. — ошибка «КОНТЕКСТ НЕ ПОМЕЩАЕТСЯ»; ответу мало места — max_tokens уменьшается. При "
    "типовом окне запрос не проверяется.",
]
ch_els, cy = [], y
for t in chain_txt:
    h = needed_height(t, CH_W, FS) + 6
    ch_els.append(box(CH_X, cy, CH_W, h, t, CODE, CODE_BG, size=FS, align="left", valign="top"))
    cy += h + 40
for a_, b_ in zip(ch_els, ch_els[1:]):
    arrow(a_, b_, CODE)


def _t_on(group, el):   # доля высоты группы на уровне центра элемента
    return (el["y"] + el["height"] / 2 - group["y"]) / group["height"]


arrow(src_group, ch_els[0], GRAY, a_side="right", b_side="left", a_t=_t_on(src_group, ch_els[0]))
arrow(src_group, ch_els[2], GRAY, a_side="right", b_side="left", a_t=_t_on(src_group, ch_els[2]))

prio_txt = (
    "ПРИОРИТЕТ ИСТОЧНИКОВ — один для всех параметров\n"
    "(его применяют resolve_model_limits() и resolve_settings())\n"
    "\n"
    "• подключения (адреса, ключи, модели, папки): переменные окружения системы > .env\n"
    "• лимиты моделей: панель (сеанс) > config.yaml > сервер / измерение > типовое значение\n"
    "• остальные параметры: панель (сеанс) > config.yaml > расчёт MINT (для [А]) > умолчание в коде\n"
    "\n"
    "Явно заданное значение (панель или config.yaml) всегда важнее найденного у сервера и рассчитанного. "
    "[А]-параметр, зафиксированный вручную, MINT не пересчитывает, но предупредит, если он больше потолка модели "
    "(limits_warnings)."
)
ph = needed_height(prio_txt, PR_W, 17) + 6
box(PR_X, y, PR_W, ph, prio_txt, DARK, "#f8f9fa", size=17, align="left", valign="top", text_color=DARK)
y = max(src_bottom, cy - 40, y + ph) + 20
y = panel_end(p1, y)
y += 40

# ======================================================================== 2. как делится окно модели
SEG = {  # цвет рамки, фон, пунктир
    "fix": ("#495057", "#e9ecef", False),     # промпт / резервы
    "ans": ("#e8590c", "#fff4e6", False),     # ответ max_tokens
    "safe": ("#868e96", "#ffffff", True),     # запас 15 %
    "bud": ("#0c8599", "#c3fae8", False),     # бюджет
    "frag": ("#1971c2", "#d0ebff", False),    # полезный текст
    "frag2": ("#6741d9", "#e5dbff", False),
    "free": ("#0c8599", "#ffffff", True),     # свободно
}


def line(points, color, dashed=False, width=2):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    x0, y0 = points[0]
    el = base("line", x0, y0, max(xs) - min(xs), max(ys) - min(ys), color, dashed=dashed, rounded=False, width=width)
    el.update({"points": [[round(px - x0, 2), round(py - y0, 2)] for px, py in points], "lastCommittedPoint": None,
               "startBinding": None, "endBinding": None, "startArrowhead": None, "endArrowhead": None})
    elements.append(el)
    return el


def widths_for(weights, total, min_w=120):
    """Пропорциональные ширины с минимумом для узких частей."""
    n = len(weights)
    fixed = [False] * n
    for _ in range(n):
        free_total = total - sum(min_w for f in fixed if f)
        free_weight = sum(w for w, f in zip(weights, fixed) if not f)
        changed = False
        for i, w in enumerate(weights):
            if not fixed[i] and free_weight and w / free_weight * free_total < min_w:
                fixed[i] = changed = True
        if not changed:
            break
    free_total = total - sum(min_w for f in fixed if f)
    free_weight = sum(w for w, f in zip(weights, fixed) if not f) or 1
    return [min_w if f else w / free_weight * free_total for w, f in zip(weights, fixed)]


def seg_bar(x, y_, total_w, segs, size=14, min_w=120):
    """segs: [(текст, вес, стиль)]. Возвращает (элементы, высота)."""
    ws = widths_for([s[1] for s in segs], total_w, min_w)
    h = max(needed_height(t, w, size) for (t, _, _), w in zip(segs, ws)) + 6
    out, cx_ = [], x
    for (t, _, st), w in zip(segs, ws):
        sc, bg, dsh = SEG[st]
        out.append(box(cx_, y_, w, h, t, sc, bg, size=size, align="center", valign="middle", dashed=dsh,
                       text_color=DARK))
        cx_ += w
    return out, h


def bracket(x1, x2, y_, label, color=DARK, size=15):
    """Скобка снизу под отрезком [x1, x2] с подписью."""
    line([(x1, y_), (x1, y_ + 12), (x2, y_ + 12), (x2, y_)], color)
    span = max(x2 - x1, 420)
    lw_ = wrap(label, int(span / (size * xl.CHAR_W)))
    tw_, th_ = text_size(lw_, size)
    tw_ = min(tw_, span)
    text_el((x1 + x2) / 2 - tw_ / 2, y_ + 18, lw_, size, color, "center", w=tw_, h=th_)
    return y_ + 18 + th_


def zoom(seg_el, x_left, x_right, y_to, color="#0c8599", y_from=None):
    """Пунктир от сегмента вниз к развёрнутой полосе."""
    yb = y_from or seg_el["y"] + seg_el["height"]
    line([(seg_el["x"], yb), (x_left, y_to)], color, dashed=True, width=1)
    line([(seg_el["x"] + seg_el["width"], yb), (x_right, y_to)], color, dashed=True, width=1)


def caption(x, y_, text, size=18, color=DARK, w=None):
    t = wrap(text, int((w or 1100) / (size * xl.CHAR_W)))
    text_el(x, y_, t, size, color)
    return y_ + text_size(t, size)[1] + 8


p2w = y
y = panel_start(y, "2. Как делится окно модели: что занимает место и сколько остаётся тексту из базы",
                "Слева — общий вид (масштаб условный), справа — те же полосы на числах: окно LLM 32768 ток., "
                "max_tokens 1500, chars_per_token 2.5, top_k 5, вход эмбеддингов и реранкера 8192 ток., "
                "Qwen3-Embedding. Узкие части на правых полосах показаны шире, чем в масштабе. Формула каждой части — "
                "колонка «Ограничения» в панели 3.")
CW = (W - 2 * PX - 60) / 2
LX, RX = PX, PX + CW + 60
text_el(LX, y, "ОБЩИЙ ВИД", 22, CODE)
text_el(RX, y, "ПРИМЕР НА ЧИСЛАХ", 22, CODE)
y += 44

# ---- чат
yl = caption(LX, y, "ЧАТ — один вызов LLM на вопрос.  Вся полоса = llm_context_tokens [ток.]")
yr = caption(RX, y, "ЧАТ, окно 32768 ток.")
yy = max(yl, yr)
L, lh = seg_bar(LX, yy, CW, [
    ("промпт, вопрос, история, сокращения\nCHAT_RESERVE 800 ток.", 1.4, "fix"),
    ("ответ\nmax_tokens [ток.]", 1.0, "ans"),
    ("запас 15 %\n(× 0.85)", 0.8, "safe"),
    ("chat_budget\nостаток → в символы", 2.6, "bud")])
R, rh = seg_bar(RX, yy, CW, [
    ("промпт и пр.\n800 ток.", 800, "fix"), ("ответ\n1500 ток.", 1500, "ans"),
    ("запас 15 %\n4 570 ток.", 4570, "safe"),
    ("chat_budget\n25 898 ток. × 2.5 = 64 744 симв.", 25898, "bud")], min_w=150)
yy += max(lh, rh) + 8
bl = bracket(LX, LX + CW, yy, "llm_context_tokens [ток.] — окно модели целиком")
br = bracket(RX, RX + CW, yy, "32 768 ток. = 800 + 1 500 + 4 570 + 25 898")
yz = max(bl, br) + 4
yy = yz + 36
zoom(L[3], LX, LX + CW, yy, y_from=yz)
zoom(R[3], RX, RX + CW, yy, y_from=yz)
L2, lh = seg_bar(LX, yy, CW, [
    ("фрагмент 1\n≤ smart_truncate_chars", 1, "frag"), ("фрагмент 2", 1, "frag"), ("…", 0.5, "frag"),
    ("фрагмент top_k", 1, "frag"), ("свободно, если фрагменты короче", 1.6, "free")])
R2, rh = seg_bar(RX, yy, CW, [
    ("1\n2500", 2500, "frag"), ("2\n2500", 2500, "frag"), ("3\n2500", 2500, "frag"), ("4\n2500", 2500, "frag"),
    ("5\n2500", 2500, "frag"), ("свободно 52 244 симв.\n(значения ограничены умолчаниями)", 52244, "free")], min_w=95)
yy += max(lh, rh) + 8
bl = bracket(LX, LX + CW, yy, "chat_budget [симв.] = top_k фрагментов + свободное место")
br = bracket(RX, RX + CW, yy, "64 744 симв.: 5 × 2500 = 12 500 занято, 52 244 свободно")
y = max(bl, br) + 40

# ---- маленькое окно
why = ("ПОЧЕМУ 32768 ток. → ≈ 64 700 симв., А 4096 ток. → ЛИШЬ ≈ 3 800 симв.\n"
       "Из окна сначала вычитаются части фиксированного размера: ответ 1500 + промпт 800 = 2300 ток. Они одинаковы "
       "для любого окна:\n"
       "• 32768 − 2300 = 30 468 ток. × 2.5 × 0.85 = 64 744 симв.  — фиксированные части заняли 7 % окна\n"
       "• 4096 − 2300 = 1 796 ток. × 2.5 × 0.85 = 3 816 симв.  — фиксированные части заняли 56 % окна\n"
       "Окно меньше в 8 раз, а бюджет — в 17 раз.")
wh = needed_height(why, CW, 16) + 6
box(LX, y, CW, wh, why, "#e8590c", "#fff4e6", size=16, align="left", valign="top", text_color=DARK)
yr = caption(RX, y, "ЧАТ, окно 4096 ток. — то же самое на маленькой модели")
R, rh = seg_bar(RX, yr, CW, [
    ("промпт и пр.\n800 ток.", 800, "fix"), ("ответ\n1500 ток.", 1500, "ans"), ("запас\n269 ток.", 269, "safe"),
    ("chat_budget\n1 527 ток. × 2.5 = 3 816 симв.", 1527, "bud")], min_w=150)
yr += rh + 40
zoom(R[3], RX, RX + CW, yr)
R2, rh = seg_bar(RX, yr, CW, [(f"{i}\n763", 1, "frag2") for i in range(1, 6)])
yr += rh + 8
yr = bracket(RX, RX + CW, yr, "3 816 симв. / 5 = 763 симв. на фрагмент: MINT уменьшит parent_size и "
                              "smart_truncate_chars до 763 и покажет это в «MINT рассчитал»")
y = max(y + wh, yr) + 50

# ---- аудит
yl = caption(LX, y, "АУДИТ ДОКУМЕНТА — один вызов LLM (проверка одного раздела).  Вся полоса = llm_context_tokens [ток.]")
yr = caption(RX, y, "АУДИТ, окно 32768 ток.: chars(32768 − 1500) = 66 444 симв.")
yy = max(yl, yr)
L, lh = seg_bar(LX, yy, CW, [
    ("ответ\nmax_tokens [ток.]", 1, "ans"), ("запас\n15 %", 0.7, "safe"),
    ("промпт с критериями\nAUDIT_RESERVE 3500 симв.", 1.3, "fix"),
    ("раздел документа\naudit_map_size", 1.1, "frag"),
    ("нормы из базы —\nцелые parent\naudit_context_max_chars", 1.4, "frag2"), ("свободно", 0.8, "free")])
R, rh = seg_bar(RX, yy, CW, [
    ("ответ\n1500 ток.", 1500, "ans"), ("запас\n4 690 ток.", 4690, "safe"),
    ("промпт\n3500 симв.", 1400, "fix"), ("раздел\n4500 симв.", 1800, "frag"),
    ("нормы ≤ 9000 симв.\n(≈ 3 целых\nparent)", 3600, "frag2"), ("свободно\n49 444 симв.", 19778, "free")],
    min_w=150)
yy += max(lh, rh) + 8
bl = bracket(L[3]["x"], LX + CW, yy, "llm_budget [симв.]")
br = bracket(R[3]["x"], RX + CW, yy, "llm_budget = 66 444 − 3 500 = 62 944 симв.")
y = max(bl, br) + 40

# ---- контроль исправлений
yl = caption(LX, y, "КОНТРОЛЬ ИСПРАВЛЕНИЙ — один вызов LLM на замечание.  Вся полоса = llm_context_tokens [ток.]")
yr = caption(RX, y, "КОНТРОЛЬ, окно 32768 ток.")
yy = max(yl, yr)
L, lh = seg_bar(LX, yy, CW, [
    ("ответ\nmax_tokens", 1, "ans"), ("запас\n15 %", 0.7, "safe"), ("промпт\n3500 симв.", 1, "fix"),
    ("замечание\n≈ 1000 симв.", 0.9, "fix"), ("нормы —\nцелые parent\naudit_context_max_chars", 1.2, "frag2"),
    ("разделы новой редакции\nreview_context_max_chars", 1.5, "frag"), ("свободно", 0.6, "free")], min_w=100)
R, rh = seg_bar(RX, yy, CW, [
    ("ответ\n1500 ток.", 1500, "ans"), ("запас\n4 690 ток.", 4690, "safe"), ("промпт\n3500", 1400, "fix"),
    ("замечание\n1000", 400, "fix"), ("нормы\n≤ 9000", 3600, "frag2"), ("разделы\n12 000 симв.", 4800, "frag"),
    ("свободно\n40 944 симв.", 16378, "free")], min_w=110)
y = yy + max(lh, rh) + 40

# ---- эмбеддинги
yl = caption(LX, y, "ЭМБЕДДИНГИ — один child при индексации.  Вся полоса = embed_max_tokens [ток.]")
yr = caption(RX, y, "ЭМБЕДДИНГИ, вход 8192 ток.: chars(8192) = 17 408 симв.")
yy = max(yl, yr)
L, lh = seg_bar(LX, yy, CW, [
    ("запас\n15 %", 0.7, "safe"), ("путь заголовков\n250 симв.", 1, "fix"), ("префикс\nдокумента", 0.8, "fix"),
    ("child_size [симв.]", 1.3, "frag"), ("свободно", 1.6, "free")])
R, rh = seg_bar(RX, yy, CW, [
    ("запас\n1 229 ток.", 1229, "safe"), ("заголовки\n250", 100, "fix"), ("префикс\n0 (Qwen3)", 1, "fix"),
    ("child\n400", 160, "frag"), ("свободно 16 758 симв.", 6703, "free")], min_w=120)
yy += max(lh, rh) + 8
bl = caption(LX, yy, "Такой же вход у раздела документа при подборе разделов (section_embed_chars) и у запроса аудита "
                     "(audit_query_chars) — числа справа.", 15, GRAY, CW)
br = caption(RX, yy, "Раздел: 0 + 4000 симв.; запрос аудита: префикс 171 симв. + 2000 — всё помещается в 17 408. "
                     "Модель с входом 512 ток. → 1 088 симв.: child 400 ещё помещается, section_embed_chars "
                     "уменьшится до 1 088.", 15, GRAY, CW)
y = max(bl, br) + 30

# ---- реранкер
yl = caption(LX, y, "РЕРАНКЕР — одна пара «запрос + документ».  Вся полоса = rerank_max_tokens [ток.]")
yr = caption(RX, y, "РЕРАНКЕР, вход 8192 ток.: chars(8192) = 17 408 симв.")
yy = max(yl, yr)
L, lh = seg_bar(LX, yy, CW, [
    ("запас\n15 %", 0.7, "safe"), ("запрос + сокращения\nrerank_query_max_chars", 1.6, "frag2"),
    ("документ с именем файла и разделом\nrerank_doc_max_chars", 1.8, "frag"), ("свободно", 1.2, "free")])
R, rh = seg_bar(RX, yy, CW, [
    ("запас\n1 229 ток.", 1229, "safe"), ("запрос\n1500", 600, "frag2"), ("документ\n800", 320, "frag"),
    ("свободно 15 108 симв.", 6043, "free")], min_w=120)
y = yy + max(lh, rh) + 50

# ---- таблица сценариев и большое окно
text_el(LX, y, "Что получится при разных моделях (EMBED_MODEL = Qwen3-Embedding, top_k = 5); значения — [симв.]", 18, DARK)
ty = y + 34
cols = ["Параметр", "4k / 512 / 512", "8k / 512 / 1k", "32k / 8k / 8k ★", "128k / 32k / 8k"]
# Значения сверяет tests/test_diagrams.py с расчётом resolve_settings(): (окно LLM, вход эмбеддингов, вход реранкера,
# символов на токен) для каждого столбца — SCENARIO_LIMITS.
SCENARIO_LIMITS = [(4096, 512, 512, 2.5), (8192, 512, 1024, 2.5), (32768, 8192, 8192, 2.5), (131072, 32768, 8192, 3.0)]
SCENARIO_ROWS = [
    ("smart_truncate_chars", "763", "2504", "3500", "3500"),
    ("parent_size ♻", "763", "2500", "2500", "2500"),
    ("parent_overlap ♻", "152", "300", "300", "300"),
    ("child_size ♻", "400", "400", "400", "400"),
    ("child_overlap ♻", "150", "150", "150", "150"),
    ("section_embed_chars", "1088", "1088", "4000", "4000"),
    ("audit_query_chars", "917", "917", "2000", "2000"),
    ("audit_map_size", "1000 ⚠", "3216", "4500", "4500"),
    ("audit_context_max_chars", "1016", "7504", "9000", "9000"),
    ("review_context_max_chars", "1000 ⚠", "2216 ▼", "12000", "12000"),
    ("rerank_query_max_chars", "362", "725", "1500", "1500"),
    ("rerank_doc_max_chars", "726", "800", "800", "800"),
]
rows = SCENARIO_ROWS
cw = [CW * 0.32] + [CW * 0.17] * 4
row_h = 26
tbl = base("rectangle", LX, ty, CW, row_h * (len(rows) + 1) + 30, GRAY, "#ffffff")
elements.append(tbl)
cxs = [LX + 14]
for w_ in cw[:-1]:
    cxs.append(cxs[-1] + w_)
for c, name in enumerate(cols):
    text_el(cxs[c], ty + 10, name, 15, DARK)
for r, row in enumerate(rows, 1):
    for c, val in enumerate(row):
        text_el(cxs[c], ty + 10 + r * row_h, val, 15,
                "#c92a2a" if ("⚠" in val or "▼" in val) else (DARK if c == 0 else "#495057"))
ty += row_h * (len(rows) + 1) + 30 + 12
foot1 = wrap("Столбцы: окно LLM / вход эмбеддингов / вход реранкера, [ток.]; символов на токен 2.5 (в последнем — "
             "3.0). ★ — типовые лимиты: значения совпадают с умолчаниями. ⚠ — модели не хватает места: MINT берёт "
             "минимум и показывает предупреждение. ▼ — сильно урезано: контроль исправлений видит малую часть новой "
             "редакции, вероятны ложные «не исправлено». 128k даёт те же значения, что 32k: умолчания — потолок "
             "(правило — панель 1).", int(CW / (15 * xl.CHAR_W)))
text_el(LX, ty, foot1, 15, GRAY)
ty += text_size(foot1, 15)[1] + 10
big_txt = (
    "БОЛЬШОЕ ОКНО LLM (200k, 1M …) — ЧТО ТОГДА\n"
    "Предела окна в MINT нет (поле в панели принимает до 4 млн токенов). Большое окно поднимает потолки, но значения "
    "не выше умолчаний: в чат уходит ≈ top_k × 2500 симв., в аудит — раздел 4500 и нормы до 9000 симв. (3–4 целых "
    "parent). Так задумано: лишний контекст добавляет шум, время и стоимость, а точность от него обычно не растёт.\n"
    "\n"
    "Чтобы использовать большое окно — поднять вручную в config.yaml:\n"
    "• больше фрагментов в чате: top_k 8–12 → [Т] прогоны --k 5 / 8 / 12 и [П] живая проверка ответов\n"
    "• больше норм в аудите: audit_context_max_chars 13 000 (5 целых parent) … 20 000+; крупнее разделы: "
    "audit_map_size 12 000–30 000 (меньше вызовов, модель видит больше документа сразу) → [П] на документах с известными "
    "замечаниями\n"
    "• контроль исправлений: review_top_sections 5–8, review_context_max_chars 30 000+; длинные ответы — max_tokens\n"
    "• parent_size ♻ обычно не трогать: больше контекста лучше набирать числом фрагментов (top_k)\n"
    "\n"
    "Окно LLM не влияет на эмбеддинги и реранкер — у них свои лимиты."
)
bh = needed_height(big_txt, CW, FS) + 6
box(RX, y, CW, bh, big_txt, "#e8590c", "#fff4e6", size=FS, align="left", valign="top", text_color=DARK)
y = max(ty, y + bh) + 10
y = panel_end(p2w, y)
y += 40

# ======================================================================== 3. справочник параметров
p3r = y
y = panel_start(y, "3. Справочник параметров: определения, значения, ограничения",
                "Единицы: ток. — токены, симв. — символы. «В панели» — диапазон ползунка (если значение из config.yaml больше, ползунок расширяется). config.yaml "
                "проверяет только тип значения; защита от несовместимых значений — в коде (колонка «Ограничения»).")
REF_W = [330, 760, 300, 160, W - 2 * PX - 330 - 760 - 300 - 160]
REF_FS = 15

# как читать колонку «По умолчанию»
how_l = (
    "КАК ЧИТАТЬ «0 = авто: ① сервер ② иначе 32768 ток.»\n"
    "Это шаги по порядку: что стоит в коде → откуда MINT берёт значение.\n"
    "• 0 — значение в коде и в config.yaml по умолчанию: «не задано — определить автоматически». Ноль, а не число, "
    "нужен, чтобы MINT отличал «администратор ничего не указал» от явного значения (приоритет — панель 1).\n"
    "• ① сервер — первый шаг: MINT спрашивает лимит у сервера модели (detect_server_info, панель 1). Ответил — "
    "берётся это число; в «Модели и лимиты» видно «Сервер: …».\n"
    "• ② иначе 32768 — сервер не сообщил (часто у корпоративных шлюзов и облачных API): берётся типовое значение — "
    "безопасная догадка (почему именно такое — справа).\n"
    "Типовое значение может не совпасть с вашей моделью: при нём MINT размер запроса не проверяет. Чем грозит "
    "ошибка — строка llm_context_tokens; лимит лучше указать вручную (панель или config.yaml)."
)
how_r = (
    "ПОЧЕМУ ИМЕННО ЭТИ ТИПОВЫЕ ЗНАЧЕНИЯ (FALLBACK_LIMITS)\n"
    "• окно LLM 32768 ток. — обычное окно открытых моделей при развёртывании (Qwen2.5 / Qwen3, Llama 3.x, "
    "Mistral на vLLM); почти все современные модели не меньше.\n"
    "• вход эмбеддингов 8192 ток. — Qwen3-Embedding, bge-m3, gte-Qwen; модели на 512 ток. — см. embed_max_tokens.\n"
    "• вход реранкера 8192 ток. — bge-reranker-v2-m3.\n"
    "• 2.5 симв./ток. — см. блок «Токены и символы» вверху.\n"
    "\n"
    "ЧИСЛО У [А]-ПАРАМЕТРА (например, 3500 симв.)\n"
    "Это умолчание. Расчёт может только уменьшить его под маленькую модель (формула — колонка «Ограничения»), "
    "но не увеличивает."
)
HW = (W - 2 * PX - 20) / 2
hh = max(needed_height(how_l, HW, 16), needed_height(how_r, HW, 16)) + 6
box(PX, y, HW, hh, how_l, CODE, CODE_BG, size=16, align="left", valign="top", text_color=DARK)
box(PX + HW + 20, y, HW, hh, how_r, CODE, CODE_BG, size=16, align="left", valign="top", text_color=DARK)
y += hh + 24


def ref_row(y_, cells, header=False, tag=None, key=None):
    hs = [needed_height(c, w, REF_FS) for c, w in zip(cells, REF_W)]
    h = max(hs + [30]) + 4
    cx_ = PX
    for k, (c, w) in enumerate(zip(cells, REF_W)):
        bg = "#e9ecef" if header else ("#ffffff" if k else (TAG[tag][1] if tag else "#ffffff"))
        if key and k == 0:
            bg = KEY_BG if key == "◆" else "#fff9db"
        tc = DARK if header or k else (TAG[tag][0] if tag else DARK)
        el = box(cx_, y_, w, h, c, GRAY if not header else DARK, bg, size=REF_FS, align="left", valign="top",
                 text_color=tc)
        if key and k == 0:
            el["strokeColor"] = KEY_SC
            el["strokeWidth"] = 4 if key == "◆" else 2
        cx_ += w
    return y_ + h


def ref_detail(y_, text):
    t = "Подробнее: " + text
    h = needed_height(t, W - 2 * PX - REF_W[0], REF_FS) + 4
    box(PX + REF_W[0], y_, W - 2 * PX - REF_W[0], h, t, KEY_SC, "#fffdf0", size=REF_FS, align="left",
        valign="top", text_color=DARK)
    return y_ + h


def ref_group(y_, title):
    box(PX, y_, W - 2 * PX, 34, title, DARK, "#dee2e6", size=16, align="left", valign="middle")
    return y_ + 34


REF = [
    ("ПОДКЛЮЧЕНИЯ — .env", [
        ("Р", "LLM_API_URL", "Базовый адрес OpenAI-совместимого API языковой модели (…/v1); к нему добавляются "
              "/chat/completions и /models.", "— (обязательно)", "—",
         "Пусто — ошибка в панели: чат, аудит и контроль не работают."),
        ("Р", "EMBED_API_URL", "Полный адрес эндпоинта эмбеддингов (…/v1/embeddings).", "— (обязательно)", "—",
         "Пусто — загрузка документов невозможна, поиск только по словам (BM25)."),
        ("Р", "RERANK_API_URL", "Полный адрес реранкера (…/v1/rerank).", "пусто — без реранкера", "—",
         "Необязателен: без него порядок задают векторный поиск и BM25."),
        ("Р", "LLM_API_KEY, EMBED_API_KEY, RERANK_API_KEY", "Ключи доступа (Bearer).", "пусто", "—",
         "Пустые EMBED_ / RERANK_ — берётся LLM_API_KEY; пустой LLM_API_KEY — запросы без авторизации."),
        ("Р", "LLM_MODEL", "Модель по умолчанию в списке «Модель ИИ» (старое имя — DEFAULT_LLM_MODEL).",
         "первая из списка сервера", "список моделей", "Список запрашивается у сервера; модель из .env добавляется в "
                                                        "список, даже если сервер её не вернул."),
        ("Р", "EMBED_MODEL ♻", "Модель эмбеддингов; записывается в manifest каждого документа.",
         "qwen3-embedding-4b", "—", "Смена — переиндексация; другая размерность векторов — векторный поиск "
                                    "выключается до переиндексации."),
        ("Р", "RERANK_MODEL", "Модель реранкера.", "bge-reranker-v2-m3", "—", "—"),
        ("Р", "CA_BUNDLE_PATH, SSL_INSECURE", "Сертификат для TLS; SSL_INSECURE = 1 отключает проверку.",
         "системный файл сертификатов (Windows — хранилище Windows); выкл.", "—",
         "Файла нет — системные сертификаты; на Windows — через truststore. SSL_INSECURE — только во внутренней "
         "сети."),
        ("Р", "KB_DIR, LOG_DIR, GLOSSARY_PATH, MINT_CONFIG", "Папка базы, папка логов и отзывов, путь к "
              "glossary.json и к config.yaml.", "~/knowledge_base; ~/mint_logs; рядом с программой", "—",
         "Лог — mint_system.log с ротацией 10 МБ × 5; отзывы пользователей — feedback.jsonl."),
        ("Р", "MINT_LANG", "Язык интерфейса, промптов и отчётов: ru или en.", "язык ОС (ru → ru, иначе en)",
         "переключатель в панели", "Переключатель меняет язык на сеанс; check_install.py тоже пишет на этом языке."),
    ]),
    ("ЛИМИТЫ МОДЕЛЕЙ — config.yaml, раздел models", [
        ("А", "llm_context_tokens", "Окно контекста LLM, токенов: всё, что модель принимает за один вызов — "
              "промпт + найденные фрагменты + история + ответ.",
         "0 = авто:\n① сервер (/models)\n② иначе 32768 ток.", "128 … 4 млн",
         "Предела сверху нет. От него: chat_budget, llm_budget — а через них потолки smart_truncate_chars, "
         "parent_size, audit_map_size, audit_context_max_chars, review_context_max_chars.",
         {"key": "◆", "detail": "главный лимит MINT. Указывайте то, что реально пропускает сервер: если шлюз режет "
          "запросы раньше окна модели — предел шлюза. Ошибка в бо́льшую сторону опаснее: MINT посчитает, что всё "
          "помещается, а сервер вернёт «ОШИБКА ШЛЮЗА: код 400» (vLLM) или молча обрежет начало промпта (Ollama). "
          "Ошибка в меньшую — только фрагменты короче, чем можно."}),
        ("А", "embed_max_tokens", "Максимальная длина входа модели эмбеддингов, токенов.",
         "0 = авто:\n① сервер (/models)\n② иначе 8192 ток.", "128 … 4 млн",
         "От него: child_size ♻, section_embed_chars, audit_query_chars, embed_input_max_chars.",
         {"key": "◆", "detail": "для моделей с входом 512 токенов (e5, ruBERT и другие BERT-подобные) обязательно "
          "указать 512, если сервер не сообщает: иначе MINT будет считать, что вход 8192, и отправлять разделы по "
          "4000 симв. (≈ 1600 токенов) — сервер их обрежет или вернёт ошибку. Смена значения меняет child_size — "
          "нужна переиндексация ♻."}),
        ("А", "rerank_max_tokens", "Максимальная длина пары «запрос + документ» у реранкера, токенов.",
         "0 = авто:\n① сервер (/models)\n② иначе 8192 ток.", "128 … 4 млн",
         "От него: rerank_query_max_chars, rerank_doc_max_chars.", {"key": "◆"}),
        ("А", "chars_per_token", "Сколько символов текста приходится на один токен; переводит лимиты моделей из "
              "токенов в символы.",
         "0 = авто:\n① измерение кнопкой\n② иначе 2.5 симв./ток.", "1.0 … 8.0",
         "Измерение принимается в пределах 1 … 8. Как измеряется и какие значения обычны — блок «Токены и "
         "символы» вверху.",
         {"key": "◆", "detail": "участвует во всех формулах, где лимит модели переводится в символы. Меньше "
          "реального — MINT перестраховывается (фрагменты короче, чем можно). Больше реального — запросы могут не "
          "поместиться в модель."}),
        ("А", "embed_query_prefix", "Инструкция перед текстом запроса для моделей эмбеддингов с инструкцией.",
         "по имени модели", "только config.yaml", "Уменьшает audit_query_chars на свою длину. Смена переиндексации "
                                                   "не требует.",
         {"key": "◇", "detail": "что это: многие модели эмбеддингов обучены на парах «вопрос — документ», где вопрос "
          "помечен особой фразой. Без пометки такая модель ищет заметно хуже (вопрос и документ «звучат» для неё "
          "одинаково). Откуда берётся: embed_prefix_preset() сравнивает имя EMBED_MODEL с таблицей "
          "EMBED_PREFIX_PRESETS — Qwen3-Embedding, gte-Qwen, e5-instruct → «Instruct: <задача поиска>\\nQuery:» "
          "(171 симв.; задача — константа EMBED_TASK: «найти фрагменты регламентов и архитектурных документов, "
          "относящиеся к вопросу или фрагменту проверяемого документа»); e5 → «query: »; nomic-embed, FRIDA, ru-en-RoSBERTa → "
          "«search_query: »; bge-m3 и все остальные → без префикса. Значение из config.yaml важнее таблицы. "
          "Где применяется: вопрос чата, начало раздела документа при поиске норм (аудит), замечание при подборе разделов "
          "(контроль). Что выбрано — видно в «Модели и лимиты»: «Префикс запроса для модели эмбеддингов (…)»."}),
        ("А", "embed_doc_prefix ♻", "Префикс перед текстом документа (e5, nomic, FRIDA).", "по имени модели",
         "только config.yaml",
         "Смена — переиндексация (сравнивается с manifest). Уменьшает child_size и section_embed_chars.",
         {"key": "◇", "detail": "пара к префиксу запроса — пометка текста документа: e5 → «passage: », nomic, FRIDA, "
          "RoSBERTa → «search_document: »; Qwen3-Embedding и bge-m3 — без префикса (у Qwen3 инструкция только у "
          "запроса). Добавляется к каждому child при индексации и к разделам новой редакции на вкладке контроля. "
          "Если модель на шлюзе названа по-своему (например, «emb-prod») и не распознана — оба префикса пустые: "
          "задайте их в config.yaml по документации модели и сравните проверкой качества до и после."}),
    ]),
    ("ПРОМЕЖУТОЧНЫЕ ВЕЛИЧИНЫ — рассчитываются в _derive(), не задаются: меняются через лимиты моделей и max_tokens", [
        ("А", "chat_budget", "Бюджет контекста чата: сколько символов найденных фрагментов помещается в окно LLM при "
              "ответе в чате — после того как из окна вычтено место под ответ и под промпт, вопрос и историю.",
         "≈ 64 700 симв.\n(окно 32768, ответ 1500)", "не задаётся",
         "= chars(llm_context_tokens − max_tokens − 800); 800 ток. — CHAT_RESERVE_TOKENS (промпт, вопрос, история). "
         "От него: smart_truncate_chars, parent_size.",
         {"key": "◆", "detail": "увеличить бюджет можно бо́льшим окном (если модель позволяет) или меньшим max_tokens. "
          "Почему окно 4096 даёт бюджет в 17 раз меньше, чем 32768, — разбор на числах в панели 2."}),
        ("А", "llm_budget", "Бюджет контекста аудита и контроля исправлений: сколько символов (раздел документа + нормы из "
              "базы + разделы новой редакции) помещается в окно LLM.",
         "≈ 62 900 симв.\n(окно 32768, ответ 1500)", "не задаётся",
         "= chars(llm_context_tokens − max_tokens) − 3500; 3500 симв. — AUDIT_RESERVE_CHARS (промпт с критериями). "
         "От него: audit_map_size, audit_context_max_chars, review_context_max_chars.", {"key": "◆"}),
        ("А", "embed_input_max_chars", "Предельная длина текста, отправляемого в модель эмбеддингов; длиннее — "
              "обрезается перед отправкой (_embed_input).",
         "≈ 17 400 симв.\n(вход 8192)", "не задаётся", "= chars(embed_max_tokens). Страховка: ни один запрос к "
                                                      "эмбеддингам не превысит вход модели."),
    ]),
    ("ЯЗЫКОВАЯ МОДЕЛЬ", [
        ("П", "temperature", "Случайность ответа LLM.", "0.1", "0.0 … 1.0",
         "Действует на ответы чата, аудит, самокритику аудита и контроль исправлений. Исключение — служебный шаг "
         "чата condense_question(): уточняющий вопрос («а для второго контура?») переписывается в самостоятельный "
         "всегда с temperature 0, чтобы поиск получал одну и ту же формулировку. К самокритике это не относится."),
        ("П", "max_tokens", "Максимальная длина ответа модели, токенов.", "1500 ток.", "256 … 8000",
         "От него: chat_budget, llm_budget.",
         {"key": "◆", "detail": "место под ответ резервируется в окне заранее, даже если ответ окажется коротким: "
          "каждые +1000 ток. ответа отнимают ≈ 2 100 симв. у chat_budget и llm_budget. На окне 32k это незаметно, "
          "на 4–8k — существенно. Модели с рассуждениями — панель 4."}),
        ("Р", "llm_timeout", "Ожидание ответа LLM на одну попытку, сек.", "90", "30 … 300",
         "Истёк — следующая попытка (llm_retries)."),
        ("У", "llm_retries", "Число попыток при таймауте и 502 / 503 / 504; на 429 — не меньше 4, с общей паузой.", "2", "1 … 5",
         "Пауза растёт: ≈ 2 с, 4 с … (+ случайная); 401 / 403 — сразу ошибка."),
        ("У", "request_timeout", "Ожидание ответа реранкера, сек.", "120", "только config.yaml", "—"),
    ]),
    ("ИНДЕКСАЦИЯ ♻", [
        ("А", "parent_size ♻", "Длина parent-фрагмента: его читает LLM.", "2500 симв.", "300 … 6000",
         "Авто ≤ chat_budget / 5 (минимум 300). В коде не меньше 200. От него: parent_overlap.",
         {"key": "◇", "detail": "parent — «единица чтения»: поиск находит маленький child, а модели отдаётся весь "
          "parent вокруг него, чтобы был контекст. Почему зависит от chat_budget: parent целиком идёт в контекст; "
          "длиннее своей доли бюджета — smart_truncate_chars обрежет его вокруг найденного места, и окружающий "
          "текст пропадёт. Делится на 5, а не на top_k: нарезка делается один раз при загрузке, а top_k меняется "
          "в каждом сеансе — 5 это типичный top_k. На окне 32k ограничение не срабатывает (64 744 / 5 = 12 949 > "
          "2500), на 4k срабатывает (→ 763). Больше parent — меньше разрывов смысла, но больше шума и меньше "
          "разных мест в том же бюджете. Режется по тексту — сначала по границе абзаца, затем строки, предложения "
          "и слова; заголовок не отрывается от своего текста. Один parent может захватить конец одного раздела и "
          "начало другого."}),
        ("А", "parent_overlap ♻", "Перекрытие соседних parent.", "300 симв.", "0 … 1000",
         "Авто ≤ parent_size / 5; в коде меньше parent_size."),
        ("А", "child_size ♻", "Длина child-фрагмента — единицы векторного поиска.", "400 симв.", "100 … 2000",
         "Авто ≤ вход эмбеддингов − 250 − префикс документа (минимум 100); 250 — путь заголовков "
         "(HEADING_RESERVE_CHARS); в коде от 50 до parent_size. От него: child_overlap.",
         {"key": "◇", "detail": "child — «единица поиска»: по нему считается вектор. Короткий child точнее "
          "совпадает с вопросом, длинный — размывается. 400 симв. (≈ 2–4 предложения) — компромисс для "
          "регламентов."}),
        ("А", "child_overlap ♻", "Перекрытие соседних child.", "150 симв.", "0 … 500",
         "Авто ≤ child_size / 2; в коде меньше child_size."),
        ("У", "embed_batch_size", "Текстов в одном запросе эмбеддингов при индексации.", "32", "только config.yaml",
         "Не меньше 1; предел — сервер эмбеддингов. Сбой пачки — по одному."),
    ]),
    ("ПОИСК", [
        ("Т", "top_k", "Сколько найденных фрагментов (parent) MINT кладёт в контекст LLM при ответе в чате. Тот же "
              "top_k берут аудит документа (нормы из базы) и контроль исправлений.",
         "0 = авто:\n4, если в базе ≤ 300 child\n5, если больше", "2 … 8",
         "Не больше rerank_top_k (отбор идёт из этих кандидатов). Сверху в коде не ограничен: больше 8 — через "
         "config.yaml. От него: smart_truncate_chars.",
         {"key": "◆", "detail": "в коде top_k = 0, то есть «выбрать автоматически»: MINT считает child-фрагменты в "
          "базе (kb_default_top_k). ≤ 300 (≈ 10–15 регламентов) → 4: пятый фрагмент обычно повтор или шум; больше → 5: "
          "ответ чаще разбросан по нескольким местам. Ползунок «Глубина поиска (Top-K)» стоит на авто-значении и "
          "меняет его на сеанс; config.yaml (search: top_k: 6) отключает автоматику.\n"
          "Связь с лимитами: фрагменты делят бюджет окна — каждый обрезается до smart_truncate_chars ≈ (окно − "
          "ответ − резерв) / top_k. Больше top_k — модель видит больше разных мест, но каждое короче. На маленьком "
          "окне top_k 8 даст обрывки (под ползунком: «Контекст чата: до ≈ N симв. (Top-K × фрагмент)»); на большом "
          "фрагменты остаются полными. В аудите действует ещё и audit_context_max_chars.\n"
          "Как подбирать: начать с авто. Часто «информация отсутствует», а ответ в базе есть → смотреть hit@3 и hit@K "
          "в report.md: правильный фрагмент на 5–8 месте → поднять top_k до 6–8. Нет его и в первой десятке → top_k "
          "не поможет: проблема в поиске или нарезке."}),
        ("Т", "initial_k", "Сколько ближайших child берёт векторный поиск.", "50", "10 … 200",
         "Не больше числа векторов в базе; несколько child одного parent дают одного кандидата."),
        ("Т", "bm25_top_k", "Сколько parent берёт поиск по словам.", "20", "5 … 100",
         "Берутся только фрагменты с баллом > 0."),
        ("Т", "rerank_top_k", "Кандидатов после слияния: идут на реранк и в отбор top_k.", "16", "4 … 40",
         "Ограничивает top_k сверху. Больше — больше запросов к реранкеру.", {"key": "◇"}),
        ("У", "rrf_constant", "Константа сглаживания слияния RRF (формула — панель 7).", "60", "10 … 120",
         "Меньше — сильнее разница между первыми местами списков."),
        ("Т", "weight_dense", "Вес векторного поиска в слиянии.", "1.0", "0 … 3", "0 — канал отключён."),
        ("Т", "weight_bm25", "Вес поиска по словам в слиянии.", "1.0", "0 … 3", "0 — канал отключён."),
        ("Т", "weight_rerank", "Вес голоса реранкера в слиянии.", "0.7", "0 … 3",
         "Только с реранкером. 0 — порядок без реранкера, его баллы остаются для «уверенность низкая».",
         {"detail": "реранкер не заменяет порядок, а голосует в слиянии наравне с векторным поиском и BM25. 0.7 — "
          "реранкер чуть слабее каждого из двух поисков; 1.5–3 — его мнение решающее."}),
        ("А", "smart_truncate_chars", "Максимальная длина одного фрагмента в контексте LLM.",
         "3500 симв. — или меньше,\nесли не помещается", "500 … 10000",
         "Авто ≤ chat_budget / top_k (минимум 500). Длиннее — фрагмент обрезается вокруг найденного места "
         "(focus_passage); ближайший заголовок выше сохраняется, у таблицы — заголовок и шапка.",
         {"detail": "при умолчаниях (parent 2500 < 3500) ничего не обрезается — лимит срабатывает только на "
          "маленьком окне или большом top_k. Обрезается вокруг найденного места: child из векторного поиска или "
          "окно, где больше всего слов вопроса. Соседние фрагменты одного документа склеиваются в один блок "
          "(merge_adjacent) без повтора перекрытия; его лимит — smart_truncate_chars × число склеенных."}),
        ("П", "max_table_parts", "Сколько частей одной таблицы может попасть в контекст.", "2", "0 … 6",
         "0 — без ограничения. Лимит мягкий: свободные места добираются частями."),
        ("Т", "use_multi_query", "Вторая формулировка вопроса от LLM; кандидаты ищутся по обеим.", "выкл.",
         "флажок", "Вопросы длиннее 1200 симв. не перефразируются."),
        ("У", "multi_query_alt_weight", "Вес результатов по второй формулировке.", "0.85", "0 … 1", "—"),
        ("У", "max_query_chars", "Максимальная длина запроса к поиску; длиннее — обрезается.", "24000 симв.",
         "только config.yaml", "—"),
        ("У", "cascade_split_chars", "Запрос длиннее делится пополам и ищется частями.", "20000 симв.",
         "только config.yaml", "Глубина деления — не больше 3."),
    ]),
    ("РЕРАНКЕР — используются, только если задан RERANK_API_URL", [
        ("Р", "rerank_max_docs", "Документов в одном запросе к реранкеру.", "10", "3 … 30",
         "Ограничение шлюза; остальные кандидаты — следующими запросами."),
        ("Р", "rerank_char_budget", "Символов в одном запросе к реранкеру.", "9000 симв.", "3000 … 60000",
         "Ограничение шлюза; один документ уходит всегда, даже если длиннее."),
        ("А", "rerank_query_max_chars", "Длина запроса (с расшифровками сокращений) для реранкера.", "1500 симв.",
         "200 … 4000", "Авто ≤ вход реранкера / 3 (минимум 200). От него: rerank_doc_max_chars.", {"key": "◇"}),
        ("А", "rerank_doc_max_chars", "Длина фрагмента документа для реранкера вместе с именем файла и разделом.",
         "800 симв.", "200 … 6000", "Авто ≤ вход реранкера − длина запроса (минимум 200); сам фрагмент не короче 150 симв."),
        ("У", "rerank_with_meta", "Добавлять имя файла, раздел и таблицу в начало текста для реранкера.", "вкл.",
         "флажок", "—"),
        ("У", "min_rerank_score", "Минимальный балл, при котором голос реранкера учитывается.", "0.15", "0 … 1",
         "Рассчитан на шкалу 0 … 1; у реранкера с другой шкалой — задать вручную."),
    ]),
    ("СИГНАЛ «УВЕРЕННОСТЬ НИЗКАЯ» — как срабатывает, см. панель 7", [
        ("Т", "low_conf_rerank", "Порог лучшего балла реранкера.", "0.30", "0 … 1",
         "С реранкером сигнал зависит только от него."),
        ("Т", "low_conf_lexical", "Только без реранкера: порог доли слов вопроса в контексте.", "0.50", "0 … 1",
         "Слова сравниваются по основам; вопросительные слова не считаются."),
        ("У", "low_conf_agree_top", "Только без реранкера: глубина совпадения векторного поиска и BM25.", "5",
         "1 … 20", "—"),
        ("У", "show_source_details", "Показывать баллы и позиции рядом с источниками в чате.", "вкл.", "флажок",
         "—"),
    ]),
    ("ЧАТ И ГЛОССАРИЙ", [
        ("П", "chat_history_turns", "Сколько прошлых пар «вопрос — ответ» учитывать для уточняющих вопросов.", "2",
         "0 … 6", "0 — без истории; ответ ассистента в истории обрезается до 1200 симв."),
        ("У", "glossary_auto", "Собирать сокращения из загруженных документов.", "вкл.", "только config.yaml", "—"),
        ("П", "glossary_in_context", "Передавать модели справочник найденных сокращений.", "вкл.", "флажок",
         "Выключить, если автоглоссарий даёт ошибочные расшифровки."),
        ("У", "glossary_max_entries", "Сокращений в справочнике для модели, не больше.", "20", "5 … 60",
         "Сначала сокращения из вопроса, затем из найденных фрагментов."),
    ]),
    ("АУДИТ ДОКУМЕНТА И КОНТРОЛЬ ИСПРАВЛЕНИЙ", [
        ("А", "audit_map_size", "Размер раздела документа на одну проверку; тот же размер — у разделов на вкладке контроля.",
         "4500 симв.", "1000 … 12000", "Авто ≤ 0.3 × llm_budget (минимум 1000). Меньше — детальнее, но больше "
                                       "вызовов LLM. От него: audit_context_max_chars.",
         {"key": "◇", "detail": "Документ режется на части по разделам до этого размера (раздел до 1,5 размера — "
          "целым), каждая проверяется отдельным вызовом LLM. Чтобы модель не писала «не указано X», когда X есть в "
          "другом разделе, к части прилагается документ целиком (audit_full_document) или оглавление."}),
        ("П", "use_self_critique", "Второй проход «контролёр» по черновику замечаний.", "вкл.", "флажок",
         "Отсеивает надуманные замечания; без него быстрее."),
        ("П", "audit_full_document", "Документ целиком в каждой проверке раздела и самокритике.", "вкл.", "флажок",
         "Только если документ помещается в окно модели; иначе — оглавление и сверка «не описано» с другими "
         "разделами."),
        ("П", "audit_merge_duplicates", "Сведение повторов замечаний моделью в конце аудита.", "вкл.", "флажок",
         "+1 вызов LLM; выключено — повторы склеиваются только по совпадению слов."),
        ("П", "audit_passes", "Проходов проверки разделов и вопросов глубокой проверки о процессе и цифрах.", "1",
         "1 … 3", "2–3 — с температурой ≥ 0,4; замечания проходов сводятся, найденное несколько раз — выше."),
        ("П", "audit_summary_max", "«Главное» в начале заключения: самые важные замечания указателями на номера.",
         "12", "0 … 30", "+1 вызов LLM (модель-редактор); 0 — без блока."),
        ("П", "audit_reasoning", "Аудит с рассуждениями модели (поверх llm_no_reasoning).", "выкл.", "флажок",
         "Ответ +6000 токенов на рассуждения, таймаут ≥ 300 с; в чате рассуждения как настроено."),
        ("У", "audit_known_abbreviations", "Общеизвестные сокращения, которые проверка сокращений не отмечает.", "—",
         "только config.yaml", "Через запятую; ГОСТ, РФ, API и подобные уже учтены."),
        ("П", "audit_deep", "Глубокая проверка: узкие вопросы модели по процессу, противоречиям, цифрам, опечаткам.",
         "вкл.", "флажок", "Десятки коротких вызовов LLM; модель среднего размера справляется с узким вопросом надёжнее, "
         "чем с аудитом главы."),
        ("П", "audit_deep_max_calls", "Не больше стольких вопросов глубокой проверки.", "60", "0 … 300",
         "0 — без лимита; первыми — процесс и цифры."),
        ("П", "audit_parallel", "Запросов аудита одновременно: разделы, вопросы глубокой проверки, пункты.", "3",
         "1 … 8", "Больше — быстрее; при ответах 429 и таймаутах — уменьшить."),
        ("П", "audit_pinned_max_chars", "Правила экспертов и карточки систем на один запрос аудита (сверх норм).",
         "20000 симв.", "0 … 60000", "Помещаются — целиком, иначе — ближайшие к тексту фрагменты; 0 — не передавать."),
        ("П", "audit_systems", "Что документ требует от каждой упомянутой системы — по её карточке.", "вкл.", "флажок",
         "+1 вызов LLM на систему, упомянутую в документе не меньше двух раз (до 5 систем)."),
        ("П", "audit_basis_docs", "Документы-основания: документы базы по ссылкам на титуле и в «Ссылочных "
         "документах» — в каждой проверке раздела.", "вкл.", "флажок",
         "Без вызовов LLM; что найдено — блок «📎 Документы-основания» на вкладке и лог; снять или добавить — там же."),
        ("П", "audit_basis_max_chars", "Фрагменты документов-оснований на один запрос аудита (сверх норм поиска).",
         "8000", "0 … 40000", "Ближайшие к разделу фрагменты; 0 — не передавать."),
        ("А", "audit_query_chars", "Сколько символов начала раздела уходит в поиск норм.", "2000 симв.", "300 … 6000",
         "Авто ≤ вход эмбеддингов − префикс запроса (минимум 300)."),
        ("А", "audit_context_max_chars", "Сколько текста норм из базы (parent целиком, суммарно) попадает в проверку "
              "одного раздела документа.", "9000 симв.", "1000 … 40000",
         "Авто ≤ llm_budget − audit_map_size (минимум 1000). Parent берутся целиком в порядке релевантности, пока "
         "сумма помещается, — остальные отбрасываются (первый — всегда); не больше top_k. От него: "
         "review_context_max_chars.",
         {"key": "◇", "detail": "пять parent по ≈ 2500 симв. с заголовками — это ≈ 13 000 > 9000: в аудит попадают "
          "3 самых релевантных, 4-й и 5-й отбрасываются и не попадают в «Использованные источники». Набор "
          "останавливается на первом непоместившемся, даже если следующий короче. Поэтому поднимать top_k ради "
          "аудита бессмысленно, пока не поднят этот лимит: для 5 целых parent нужно ≈ 13 000–13 500. Тот же лимит — "
          "у норм на вкладке контроля исправлений."}),
        ("П", "review_top_sections", "Сколько разделов новой редакции получает модель на одно замечание.", "3",
         "1 … 8", "Ограничены review_context_max_chars."),
        ("А", "review_context_max_chars", "Объём этих разделов на одно замечание.", "12000 симв.", "1000 … 50000",
         "Авто ≤ llm_budget − audit_context_max_chars − 1000 (минимум 1000); первый раздел передаётся всегда."),
        ("А", "section_embed_chars", "Сколько символов раздела уходит в эмбеддинг при подборе разделов.", "4000 симв.",
         "300 … 8000", "Авто ≤ вход эмбеддингов − префикс документа (минимум 300)."),
    ]),
]
y = ref_row(y, ["Параметр", "Что это", "По умолчанию", "В панели", "Ограничения и зависимости"], header=True)
for g_title, rows_ in REF:
    y = ref_group(y + 8, g_title)
    for row_ in rows_:
        tag_, name_, what_, dflt_, ui_, lim_ = row_[:6]
        extra = row_[6] if len(row_) > 6 else {}
        key = extra.get("key")
        label = f"{key} [{tag_}] {name_}" if key else f"[{tag_}] {name_}"
        y = ref_row(y, [label, what_, dflt_, ui_, lim_], tag=tag_, key=key)
        if extra.get("detail"):
            y = ref_detail(y, extra["detail"])
y += 20
const = ("Прочие константы кода (меняются только в коде mint/): сокращение — от 2 до 12 символов, не меньше 2 "
         "заглавных; переписанный уточняющий вопрос — до 300 токенов. Остальные константы указаны там, где действуют: "
         "запас и резервы окна — в строках параметров выше и в блоке «Токены и символы», алгоритм поиска (BM25, "
         "расширение запроса, дедупликация) — в панели 7.")
const_w = wrap(const, int((W - 2 * PX - 2 * xl.PAD) / (16 * xl.CHAR_W)))
chh = text_size(const_w, 16)[1] + 2 * xl.PAD + 4
box(PX, y, W - 2 * PX, chh, const, TAG["У"][0], TAG["У"][1], size=16, align="left", valign="top", text_color=DARK)
y += chh + 10
y = panel_end(p3r, y)
y += 40

# ======================================================================== 3. бизнес-особенности
p3 = y
y = panel_start(y, "4. Особенности компании → на что влияют и как настраивать",
                "Что из исходных условий меняет настройки MINT. Пункты с [Т] сравниваются проверкой качества "
                "до и после изменения.")
biz = [
    ("Размер базы: сколько документов и фрагментов",
     "НЕ влияет на размеры фрагментов, пороги реранкера, промпты. ВЛИЯЕТ на: авто-top_k (панель 3); глубину "
     "кандидатов initial_k / bm25_top_k / rerank_top_k (похожих документов больше — правильный дальше в списке); "
     "пороги «уверенность низкая»; память и время (панель 9).",
     "[Т] если правильный фрагмент всё чаще «> 10» — initial_k 80–100, bm25_top_k 30, rerank_top_k 24; "
     "перекалибровать low_conf_rerank / low_conf_lexical. [Р] top_k задать явно, если авто-выбор не устраивает."),
    ("Структура документов: стили заголовков Word",
     "Без стилей «Заголовок 1–3» Docling не находит разделы (collect_structure): в ссылках только имя файла, "
     "раздел в контексте и в оценке не виден.",
     "Проставить стили в исходниках и переиндексировать ♻. Нумерованные заголовки обычным стилем MINT пока не "
     "распознаёт."),
    ("Длина разделов: короткие пункты регламентов или длинные описания",
     "parent охватывает несколько коротких пунктов — точные вопросы «тонут» в соседнем тексте; длинным связным "
     "описаниям, наоборот, не хватает контекста.",
     "[Т] на копии базы ♻: короткие пункты и точные вопросы — parent_size 1500–2000; длинные описания — 3000–3500 "
     "(если окно LLM позволяет: MINT не даст выйти за потолок). Сравнить --compare."),
    ("Много таблиц: матрицы требований, SLA, перечни",
     "Большая таблица делится на части с повтором шапки; часть из них может не попасть в контекст "
     "(max_table_parts).",
     "[П] max_table_parts 3–4, если вопросы часто про таблицы; [Т] добавить такие вопросы в набор eval и "
     "смотреть hit@K."),
    ("Много сокращений и внутренних названий систем",
     "Эмбеддинги не знают внутренних названий — их находят BM25 и глоссарий.",
     "[Р] glossary.json для сокращений, которых нет в документах (шаг 4, панель 5); [Т] если «только BM25» "
     "заметно лучше «только dense» — weight_bm25 1.3–1.5."),
    ("Несколько редакций одного документа в базе",
     "Дубли занимают места в top_k; дедупликация убирает только совпадающие фрагменты; модель может сослаться на "
     "устаревшую редакцию.",
     "[Р] держать в базе только действующие редакции (старые удалять); в именах файлов — номер редакции; "
     "иначе [Т] top_k выше."),
    ("Как спрашивают пользователи: термины, длинные ситуации, диалог",
     "Короткие термины и коды лучше ищет BM25; длинные «своими словами» — вектор; уточнения «а для второго "
     "контура?» требуют истории.",
     "[Т] веса weight_dense / weight_bm25, use_multi_query для расплывчатых вопросов; [П] chat_history_turns "
     "0 / 2 / 3. Набор вопросов для eval — из реальных обращений."),
    ("Язык документов: русский, английский, смешанные",
     "BM25 приводит слова к основам русским (Snowball) или английским (Porter2) стеммером — по каждому слову; коды "
     "ищутся точно; смысловой поиск зависит от модели эмбеддингов.",
     "[Р] многоязычная модель эмбеддингов (Qwen3-Embedding, bge-m3, multilingual-e5) ♻ — смена модели требует "
     "переиндексации; MINT_LANG — язык интерфейса, промптов и отчётов; «Определить у сервера» — после загрузки "
     "документов на другом языке."),
    ("Требования к ответам: строгость, длина, ссылки",
     "Строгость — temperature; длина — max_tokens (место под ответ отнимается у контекста, панель 2).",
     "[П] temperature 0–0.2; max_tokens — по длине типичного ответа; ссылки [файл, раздел] — в "
     "CHAT_SYSTEM_PROMPT / CHAT_SYSTEM_PROMPT_EN; ссылки мимо контекста check_citations() помечает ⚠."),
    ("Модели компании: окно LLM, входы эмбеддингов и реранкера, рассуждения",
     "Определяют все [А]-параметры через потолки (панели 1–2); модели с рассуждениями тратят max_tokens и на "
     "<think> (strip_reasoning убирает рассуждения из ответа).",
     "[П] модели с рассуждениями: max_tokens 3000–4000 (иначе ответ обрывается — «Ответ модели обрезан»), "
     "llm_timeout 150–180; новая модель эмбеддингов ♻ — переиндексация (kb_document_status покажет)."),
    ("Корпоративный шлюз: лимиты запросов, таймауты, TLS",
     "HTTP 400 от реранкера при больших пачках, 429 / 504 при нагрузке, собственный сертификат.",
     "[Р] rerank_max_docs, rerank_char_budget; llm_timeout, llm_retries; CA_BUNDLE_PATH."),
    ("Справка о системах: что умеют, планы, ограничения",
     "Без карточек систем аудит не знает их возможностей и не может проверить, что документ требует от системы "
     "(answer_system) и не противоречит ли её ограничениям.",
     "[Р] черновик карточки по базе — кнопка «Собрать черновик карточки системы по базе» (draft_system_card): "
     "эксперт проверяет, дописывает пробелы и загружает в базу с отметкой «Карточки систем»; [П] "
     "audit_pinned_max_chars, если карточек много."),
    ("Регламент проверки документов: критерии, чек-листы, объём документа",
     "Критерии и чек-листы задают, что ищет аудит; размер раздела — детальность и число вызовов LLM.",
     "[Р] общие критерии — поле на вкладке «Аудит документа» (по умолчанию DEFAULT_AUDIT_FOCUS), чек-листы по "
     "типам документов — checklists.yaml (файл вне папки программы — путь в MINT_CHECKLISTS); пункты, важные для конкретного документа, — в поле «Особое внимание»; "
     "[П] audit_map_size и use_self_critique — на живой проверке (шаг 9, панель 5)."),
    ("Нагрузка: число одновременных пользователей",
     "Все сеансы делят шлюз LLM; разбор документов и запись в базу идут по очереди (панель 6).",
     "[Р] лимиты шлюза и llm_retries; загрузку больших пакетов документов — вне часов пик."),
]
bw = [440, 900, W - 2 * PX - 440 - 900 - 2 * 16]
hdr, hh = row_boxes(PX, y, bw, ["Особенность компании", "На что влияет в MINT", "Как настраивать"],
                    (DARK, "#e9ecef"), gap=16, size=17, min_h=30)
y += hh + 12
for k, (a_, b_, c_) in enumerate(biz):
    _, rh = row_boxes(PX, y, bw, [a_, b_, c_],
                      [(DARK, "#ffffff"), (DARK, "#ffffff"), (DARK, "#f8f9fa")], gap=16, size=FS, text_color=DARK)
    y += rh + 10
y += 10
y = panel_end(p3, y)
y += 40

# ======================================================================== 4. порядок настройки
p4 = y
y = panel_start(y, "5. Порядок настройки у себя",
                "Шаги 6–8 повторяются: база выросла в 2 раза, новый тип документов, другая модель эмбеддингов или "
                "реранкера, изменены parent_size / child_size.")
steps = [
    "1. Подключения\n.env: адреса, ключи, модели, KB_DIR, сертификат. check_install.py без ошибок; в панели нет "
    "красных ошибок, реранкер «доступен» или «не подключён».",
    "2. Лимиты моделей\n«Модели и лимиты» → «Определить у сервера». Чего сервер не сообщает — в config.yaml "
    "(models). Проверить «MINT рассчитал» и предупреждения.",
    "3. Документы\nЗагрузить. Сообщения загрузки: «Распознано заголовков: N» (0 — нет стилей, панель 4), "
    "«Пропущено … чанков» — сбой эмбеддингов.",
    "4. Сокращения\nСписок «Сокращения» в панели: неточные расшифровки и недостающие сокращения — в glossary.json.",
    "5. Набор вопросов\nКнопка «Проверка качества» на боковой панели: MINT составит черновик — переписать своими "
    "словами, добавить реальные вопросы и 5–10 без ответа в базе. Всего 40–60.",
    "6. Точка отсчёта\n«Запустить проверку» → итоги на странице; report.md, details.csv, summary.json — в LOG_DIR/eval "
    "(в консоли — eval_search.py questions.csv).",
    "7. Настройка по отчёту\n«Что поменять» → «Применить в этой сессии»; закрепить в config.yaml: weight_rerank, веса "
    "dense / BM25, пороги low_conf, top_k, multi-query.",
    "8. Проверка\nСледующая проверка сравнивается с прошлой (▲▼; в консоли — --compare): MRR и hit@K выросли, "
    "ложные тревоги не выросли; разница не случайна (p < 0.05).",
    "9. Живая проверка\n15–20 ответов в чате; аудит 3–5 документов с известными замечаниями; контроль — пары редакций. "
    "Подстроить [П]-параметры.",
]
sw = (W - 2 * PX - 8 * 24) / 9
styles = [(TAG["Р"][0], TAG["Р"][1])] * 2 + [(TAG["П"][0], TAG["П"][1])] * 2 + [(TAG["Т"][0], TAG["Т"][1])] * 4 + \
         [(TAG["П"][0], TAG["П"][1])]
st_els, sh = row_boxes(PX, y, [sw] * 9, steps, styles, gap=24, size=15)
for a_, b_ in zip(st_els, st_els[1:]):
    arrow(a_, b_, GRAY, a_side="right", b_side="left")
y += sh + 30
ev = ("Как работает проверка качества — mint/evaluation.py: кнопка «Проверка качества» на боковой панели и "
      "eval_search.py в консоли (тот же код поиска, что в чате; база и сервисы — настоящие; LLM — только для черновика "
      "вопросов, ответов чата и multi-query)\n"
      "generate_questions(): по фрагменту — вопрос на языке фрагмента и дословная цитата → таблица вопросов: правка, "
      "свои вопросы; rows_to_questions() и markup_problems() — разметка, которая никогда не засчитается → "
      "request_cache() (каждый запрос к сервисам — один раз на все варианты) → build_configs(): только dense, только "
      "BM25, гибрид, гибрид + реранкер 0.35 / 0.7 / 1 / 1.5 / 3 → run_question(): search_parent_child() на глубину 10 "
      "+ diagnostics при top_k → is_relevant(): файл + раздел (в пути или заголовком внутри фрагмента) + фраза → "
      "metrics(): hit@1, hit@3, hit@K, MRR, ложные тревоги → paired() + sign_test_p(): на скольких вопросах "
      "конфигурации расходятся и случайна ли разница (критерий знаков) → calibrate(): порог по тому же правилу, что в "
      "поиске (is_low_confidence) → check_answers() по желанию (1–3 раза): ответ чата (answer_question), ссылка на "
      "нужный документ, ссылки мимо найденного, ложное и честное «информации нет» (chat_no_info), ошибка поиска или "
      "модели; compare_answers() — с прошлой проверкой ответов по вопросам и версии промптов → recommendations(): что поменять → save_run(): report.md, details.csv "
      "без пустых ячеек, summary.json, questions.csv — в LOG_DIR/eval.")
eh = needed_height(ev, W - 2 * PX, FS) + 6
box(PX, y, W - 2 * PX, eh, ev, TAG["Т"][0], TAG["Т"][1], size=FS, align="left", valign="top", text_color=DARK)
y += eh + 10
y = panel_end(p4, y)
y += 40

# ======================================================================== 5. индексация
p5 = y
y = panel_start(y, "6. Устройство: добавление документов в базу",
                "Боковая панель «Добавить документы в базу» → process_and_add_to_kb() для каждого файла. "
                "Эмбеддинги считаются без блокировки базы, слияние и запись — под kb_write_lock().")
idx_txt = [
    "parse_document()\nпо расширению: .docx — docling_convert() (один DocumentConverter на процесс, по очереди); "
    ".pdf — parse_pdf() без моделей; .md, .txt — parse_markdown(), parse_plain_text().",
    "collect_structure()\nобход iterate_items(): section_header / title → стек заголовков, heading_path_str(); "
    "table → markdown и подпись; колонтитулы и рисунки пропускаются. Сбой → collect_structure_flat() без "
    "заголовков.",
    "build_parent_chunks()\nтекст одним потоком с «## заголовками» → split_with_overlap_pos(parent_size ♻, "
    "parent_overlap ♻; разрез по абзацу, строке, предложению, слову; заголовок — со своим текстом) → в каждом "
    "parent child (child_size ♻, child_overlap ♻); путь заголовков child — по его "
    "позиции (bisect). Таблицы: clean_table_markdown() → split_table_markdown() по строкам с повтором шапки.",
    "index_parsed_document()\nвход эмбеддинга = embed_doc_prefix ♻ + путь заголовков + child → "
    "get_query_embeddings_batch() (пачками по embed_batch_size; _embed_input() обрезает до embed_input_max_chars) "
    "→ l2_normalize().",
    "Запись под kb_write_lock()\nперечитать базу, убрать прежнюю версию файла, проверить размерность векторов → "
    "IndexFlatL2 → _commit_kb(): временная папка + os.replace → save_bm25_index() → rebuild_auto_glossary() "
    "(extract_abbreviations → build_auto_glossary).",
]
iw = (W - 2 * PX - 4 * 40) / 5
i_els, ih = row_boxes(PX, y, [iw] * 5, idx_txt, (CODE, CODE_BG), gap=40, size=FS)
for a_, b_ in zip(i_els, i_els[1:]):
    arrow(a_, b_, CODE, a_side="right", b_side="left")
y += ih + 70
store_txt = [
    "child_index.faiss\nвекторы child, нормированы (поиск по косинусу)",
    "child_metadata.pkl\nparent_id, source, page, text child",
    "parent_store.json\nтекст parent, heading_path, type, section, page",
    "bm25_index.pkl\nосновы слов, позиции; подпись формата (иначе пересборка)",
    "auto_glossary.json\nсокращения из документов",
    "manifest.json\nembed_model, embed_dim, префикс, parent / child для каждого документа",
    "sources/\nоригиналы документов для переиндексации",
]
sw2 = (W - 2 * PX - 32 - 6 * 20) / 7
s_els, s_h = row_boxes(PX + 16, y + 46, [sw2] * 7, store_txt, (STORE, STORE_BG), gap=20, size=15)
st_group = base("rectangle", PX, y, W - 2 * PX, s_h + 46 + 16, DARK, "#ffec99", dashed=True)
elements.insert(elements.index(s_els[0]), st_group)
text_el(PX + 16, y + 12, "Хранилище — папка KB_DIR", 18, DARK)
w_el = i_els[4]
arrow(w_el, st_group, DARK, label="запись", a_side="bottom", b_side="top",
      b_t=(w_el["x"] + w_el["width"] / 2 - st_group["x"]) / st_group["width"])
y += s_h + 46 + 16 + 30
maint = ("Обслуживание и чтение базы\n"
         "• kb_document_status(): сравнивает manifest с текущими настройками — «другая модель эмбеддингов» (векторный "
         "поиск по документу не работает) или «другая нарезка / загружен до v18».\n"
         "• reindex_documents(): по sources/; если сменилась размерность векторов — _clear_kb_index() и сборка заново. "
         "delete_document_from_kb() — удаление с оригиналом.\n"
         "• load_kb_snapshot(): кэш по времени изменения файлов, короткая блокировка на чтение; normalized_index() "
         "нормирует старую базу в памяти. load_bm25_for(): пересборка при смене формата или набора фрагментов. "
         "load_glossary(): glossary.json важнее автоглоссария, старый формат v17 понимается.")
mh2 = needed_height(maint, W - 2 * PX, FS) + 6
box(PX, y, W - 2 * PX, mh2, maint, CODE, "#ffffff", size=FS, align="left", valign="top", text_color=DARK)
y += mh2 + 10
y = panel_end(p5, y)
y += 40

# ======================================================================== 6. поиск
p6 = y
y = panel_start(y, "7. Устройство: поиск search_parent_child() и ответ в чате",
                "Шаги общие для чата, аудита (build_norms_context) и контроля исправлений; ответ LLM — только в чате. "
                "Параметры названы по имени — значения и категории в справочнике (панель 3).")
r1 = [
    ("Вопрос пользователя", 230),
    ("chat_history() + condense_question()\nтолько в чате: последние chat_history_turns пар «вопрос — "
     "ответ»; уточнение → самостоятельный вопрос (CONDENSE_SYSTEM).", 430),
    ("analyze_query()\nвопросы «что такое X», «состав X», «what is X», «components of X» (до 300 симв.): предмет X → буст точной фразы; слова "
     "расширения ×0.3, слова предмета +0.5 — только в BM25. expand_query_multi() — если use_multi_query.", 470),
]
x = PX
r1_els = []
h_r1 = max(needed_height(t, w, FS) for t, w in r1) + 8
DB_W = 620
h_db = []
dense_t = ("Вектор: _query_vector()\nembed_query_prefix + вопрос → эмбеддинг → l2_normalize() → FAISS "
           "search: initial_k child → их parent; best_child — текст для реранкера. Нет эмбеддинга или "
           "другая размерность — канал выключается, работает BM25.")
bm25_t = ("Слова: LightweightBM25.get_scores()\nосновы слов (russian_stem — кириллица от 5 букв, english_stem "
          "— латиница от 4 букв), без стоп- и вопросительных слов (RU и EN); + Glossary.bm25_terms() ×0.5; k1 1.5, b 0.75, IDF ≥ 0.25; точная фраза +10 (до 8 "
          "слов); соседние слова вопроса рядом (≤ 3, до 12 значимых слов) +2 → bm25_top_k.")
hd, hb = needed_height(dense_t, DB_W, FS) + 6, needed_height(bm25_t, DB_W, FS) + 6
row1_h = max(h_r1, hd + hb + 24)
for t, w in r1:
    r1_els.append(box(x, y, w, row1_h, t, CODE, CODE_BG, size=FS, align="left", valign="top"))
    x += w + 40
d_el = box(x, y, DB_W, hd, dense_t, CODE, CODE_BG, size=FS, align="left", valign="top")
b_el = box(x, y + row1_h - hb, DB_W, hb, bm25_t, CODE, CODE_BG, size=FS, align="left", valign="top")
x += DB_W + 40
rrf_t = ("Слияние RRF\nвклад списка = вес / (rrf_constant + место): weight_dense, weight_bm25 → "
         "rerank_top_k кандидатов.")
rrf_el = box(x, y, W - PX - x, row1_h, rrf_t, CODE, CODE_BG, size=FS, align="left", valign="top")
for a_, b_ in zip(r1_els, r1_els[1:]):
    arrow(a_, b_, CODE, a_side="right", b_side="left")
arrow(r1_els[-1], d_el, CODE, a_side="right", b_side="left", a_t=0.25)
arrow(r1_els[-1], b_el, CODE, a_side="right", b_side="left", a_t=0.75)
arrow(d_el, rrf_el, CODE, a_side="right", b_side="left", b_t=0.25)
arrow(b_el, rrf_el, CODE, a_side="right", b_side="left", b_t=0.75)
y += row1_h + 80

rr_t = ("Реранкер (если задан RERANK_API_URL)\nGlossary.enrich_query(); rerank_document(): имя файла и раздел + "
        "child с окружением (passage_around) или окно с наибольшей плотностью слов (best_window), до "
        "rerank_doc_max_chars → rerank_scores(): все кандидаты пачками (rerank_max_docs, rerank_char_budget); "
        "сбой части пачек — баллы не учитываются. Голос: балл ≥ min_rerank_score → + weight_rerank / "
        "(rrf_constant + место).")
sel_t = ("Отбор top_k\nбез повторов (файл + первые 80 симв.); не больше max_table_parts частей одной "
         "таблицы.")
ctx_t = ("Контекст\nmerge_adjacent(): соседние фрагменты одного документа — один блок в порядке текста; "
         "_source_header(): файл | раздел в начале фрагмента | далее во фрагменте (inner_headings, до 8) | "
         "таблица | стр.; focus_passage(): длиннее smart_truncate_chars — вокруг найденного места. В списке "
         "источников — раздел, где найдено место (section_at).")
conf_t = ("Сигнал «уверенность низкая»\nis_low_confidence(): с реранкером — его лучший балл < low_conf_rerank; "
          "без реранкера — доля слов вопроса в контексте < low_conf_lexical и dense с BM25 не совпали в "
          "топ-low_conf_agree_top → LOW_CONFIDENCE_NOTE в начале контекста.")
ans_t = ("Ответ (чат)\nGlossary.reference_block() до glossary_max_entries; chat_user_content(); "
         "ask_llm(chat_system_prompt() — RU / EN, история): temperature, max_tokens; strip_reasoning() убирает "
         "<think>; finish_reason = length → пометка «ответ обрезан»; check_citations(): ссылки [файл, раздел] "
         "сверяются с контекстом, неверные — ⚠ и предупреждение под ответом.")
RR_W, SEL_W, CC_W = 720, 380, 620
hrr = needed_height(rr_t, RR_W, FS) + 6
hc1, hc2 = needed_height(ctx_t, CC_W, FS) + 6, needed_height(conf_t, CC_W, FS) + 6
row2_h = max(hrr, hc1 + hc2 + 24, needed_height(ans_t, W - 2 * PX - RR_W - SEL_W - CC_W - 120, FS) + 6)
x = PX
rr_el = box(x, y, RR_W, row2_h, rr_t, CODE, CODE_BG, size=FS, align="left", valign="top", dashed=True)
x += RR_W + 40
sel_el = box(x, y, SEL_W, row2_h, sel_t, CODE, CODE_BG, size=FS, align="left", valign="top")
x += SEL_W + 40
ctx_el = box(x, y, CC_W, hc1, ctx_t, CODE, CODE_BG, size=FS, align="left", valign="top")
conf_el = box(x, y + row2_h - hc2, CC_W, hc2, conf_t, CODE, CODE_BG, size=FS, align="left", valign="top")
x += CC_W + 40
ans_el = box(x, y, W - PX - x, row2_h, ans_t, "#f08c00", "#fff4e6", size=FS, align="left", valign="top",
             text_color=DARK)
mid_y = y - 40
arrow(rrf_el, rr_el, CODE, a_side="bottom", b_side="top", b_t=0.5,
      via=[(rrf_el["x"] + rrf_el["width"] / 2, mid_y), (rr_el["x"] + rr_el["width"] / 2, mid_y)])
arrow(rr_el, sel_el, CODE, a_side="right", b_side="left")
arrow(sel_el, ctx_el, CODE, a_side="right", b_side="left", a_t=0.25)
arrow(sel_el, conf_el, CODE, a_side="right", b_side="left", a_t=0.75)
arrow(ctx_el, ans_el, "#f08c00", a_side="right", b_side="left", b_t=0.25)
arrow(conf_el, ans_el, "#f08c00", a_side="right", b_side="left", b_t=0.75)
y += row2_h + 24
text_el(PX, y, "Реранкер с пунктирной рамкой — необязательный: без него порядок задают шаги «Вектор», «Слова» и "
               "«Слияние RRF». Нормализация слов (normalize_token: russian_stem / english_stem) общая для индекса BM25, запроса и "
               "глоссария.", 16, GRAY)
y += 40
y = panel_end(p6, y)
y += 40

# ======================================================================== 7. аудит и контроль исправлений
p7 = y
y = panel_start(y, "8. Устройство: аудит документа, контроль исправлений и черновик карточки системы",
                "Вкладки «Аудит документа» и «Контроль исправлений», кнопка черновика карточки на боковой панели. "
                "Сколько вызовов сервисов уходит на раздел, замечание и карточку — панель 9.")
text_el(PX, y, "АУДИТ ДОКУМЕНТА — вкладка «Аудит документа», настройки — блок «⚙️ Настройки аудита» на ней", 20,
        "#1971c2")
y += 36
audit = [
    "run_audit()\naudit_cfg(): audit_reasoning — без выключателя рассуждений, max_tokens + 6000, таймаут ≥ 300 с; "
    "reasoning_on() — включатель в запросе. record_answers(): каждый запрос и ответ модели слово в слово.",
    "document_to_markdown()\n.docx — Docling → export_to_markdown() → clean_docling_markdown() (повторы "
    "объединённых ячеек) → compact_markdown_tables() (без выравнивания); .pdf — parse_pdf() → blocks_to_markdown().",
    "split_document_parts()\nпо разделам: заголовок с текстом и таблицами; мелкие — вместе до audit_map_size, "
    "раздел до 1,5 лимита — целым; большая таблица — по строкам с шапкой. document_mode(): документ целиком, если "
    "помещается в окно, иначе document_outline(). «Весь документ одним запросом» — whole_document_part().",
    "Нормы\n«особое внимание» → special_focus_norms(): один поиск на аудит, до 2 parent (низкая уверенность — "
    "нет). Для раздела build_norms_context(): smart_truncate(раздел, audit_query_chars) → search_parent_child() → "
    "сначала нормы по особому вниманию, затем раздела; целые parent до audit_context_max_chars; нет — "
    "NO_NORMS_NOTE. select_pinned(): правила экспертов и карточки — до audit_pinned_max_chars. "
    "basis_references() → find_basis_documents(): документы-основания по шифру и названию — их ближайшие к "
    "разделу фрагменты до audit_basis_max_chars.",
    "MAP\naudit_section(): документ целиком или оглавление + location_line() + часть → ask_llm() → "
    "parse_findings() (подпункты — к своему замечанию) → finding_from_line(); с оглавлением — verify_absence(). "
    "Разделы — параллельно (audit_parallel).",
    "Самокритика\nuse_self_critique: critique_findings() — CRITIQUE_SYSTEM, документ целиком + «особое внимание» "
    "(такие замечания удаляются только при опровержении) → JSON {verdict, severity, category, quote}; цитата "
    "сверяется quote_in_text().",
    "Глубокая проверка\n_run_deep(): find_processes() — шаги из таблицы операций, списка шагов или подразделов "
    "«Шаг N» → build_deep_tasks() → limit_tasks(): не больше audit_deep_max_calls → run_tasks(): пары шагов, "
    "требования, границы, утверждения частей → conflict_tasks(): противоречия; цифры — quantity_calculations(); "
    "опечатки.",
    "Проходы 2–3\n_run_passes() (audit_passes): разделы и вопросы PASS_DEEP_KINDS ещё раз с температурой ≥ "
    "PASS_TEMPERATURE (0,4); в origins — «#p2», «#p3»: найденное несколькими проходами считается подтверждённым.",
]
aw = (W - 2 * PX - 7 * 30) / 8
a_els, ah = row_boxes(PX, y, [aw] * 8, audit, ("#1971c2", "#e7f5ff"), gap=30, size=15)
for a_, b_ in zip(a_els, a_els[1:]):
    arrow(a_, b_, "#1971c2", a_side="right", b_side="left")
y += ah + 70
audit2 = [
    "Пункты\nfound_so_far_block(): замечания других проверок (до 12 000 симв.) → answer_focus_point(): «особое "
    "внимание» и чек-лист — ответ по документу, новые замечания, «из документа не ясно»; answer_system(): что "
    "документ требует от системы с карточкой (audit_systems).",
    "Повтор и проверки без модели\n_recheck(): разделы, где модель не ответила, — ещё раз с retry_timeout(). "
    "check_abbreviations(), check_formatting() — ещё до проверки разделов; unverified_refs() и check_citations(): ссылки и цифры замечаний — "
    "в документе и нормах.",
    "REDUCE: повторы\nmodel_findings() → collect_unique_findings() (основы ≥ 80 %, в кусках одного раздела — "
    "section_runs() — ≥ 40 %; steps_conflict() — разные шаги не склеиваются) → clean_typos() (без модели) → merge_duplicate_findings() (audit_merge_duplicates, +1 вызов): "
    "замечания одного ответа и о разных шагах не сливаются.",
    "Разделы\nsplit_minor_findings(): главное, мелкие, опечатки → group_by_section(): по разделам документа, в его "
    "порядке; corroboration() — сколько проверок нашли замечание.",
    "«Главное»\nsummary_candidates() → select_summary() (audit_summary_max, +1 вызов): модель-редактор выбирает "
    "важное и пишет суть строкой со ссылкой на номер; не ответила — _summary_fallback(): по подтверждению и "
    "критичности.",
    "Заключение и лог\nbuild_final_report(): «Главное», замечания по разделам, ответы на пункты, системы; "
    "audit_log_markdown(): лог с настройками прогона; raw_answers_markdown(): сырые ответы модели .md.",
    "Документ с замечаниями\nannotate_docx_with_findings(): _locate_by_quote() → _isolate_range() → add_comment(); без "
    "цитаты — _locate_by_words() (≥ 2 слов и ≥ 30 %, однозначно); иначе — список в начале документа.",
    "Сверка с эталоном\ncompare_with_reference(): модель сверяет каждый пункт эталона с замечаниями аудита — то же "
    "место и суть: найдено, частично, пропущено; пачками, пропущенное переспрашивается → reference_markdown().",
]
b_els, bh = row_boxes(PX, y, [aw] * 8, audit2, ("#1971c2", "#e7f5ff"), gap=30, size=15)
for a_, b_ in zip(b_els, b_els[1:]):
    arrow(a_, b_, "#1971c2", a_side="right", b_side="left")
turn_y = y - 35
arrow(a_els[-1], b_els[0], "#1971c2", a_side="bottom", b_side="top",
      via=[(a_els[-1]["x"] + aw / 2, turn_y), (b_els[0]["x"] + aw / 2, turn_y)])
y += bh + 40
text_el(PX, y, "КОНТРОЛЬ ИСПРАВЛЕНИЙ — вкладка «Контроль исправлений»", 20, "#6741d9")
y += 36
review = [
    "document_to_markdown() → split_into_sections()\nновая редакция документа, разделы до audit_map_size.",
    "build_section_index()\nэмбеддинги разделов (до section_embed_chars) + LightweightBM25 по разделам; один "
    "раз на документ.",
    "verify_remark(): подбор\nнормы — build_norms_context() (галочка «база знаний»); pick_sections_for_remark(): "
    "косинус + BM25 + реранкер (best_window), RRF → review_top_sections разделов до "
    "review_context_max_chars.",
    "review_prompt() → ask_llm()\nJSON {status, quote, comment}.",
    "parse_verification()\n«исправлено» и «частично» засчитываются, только если quote_in_text() нашла цитату в "
    "разделах; иначе «не удалось проверить».",
    "build_matrix_markdown() / generate_word_matrix()\nматрица контроля .md и .docx.",
]
vw = (W - 2 * PX - 5 * 30) / 6
v_els, vh = row_boxes(PX, y, [vw] * 6, review, ("#6741d9", "#f3f0ff"), gap=30, size=15)
for a_, b_ in zip(v_els, v_els[1:]):
    arrow(a_, b_, "#6741d9", a_side="right", b_side="left")
y += vh + 24
_n8 = wrap("Ошибки сервисов не превращаются в «чисто»: is_llm_error() — раздел попадает в «не удалось проверить», "
           "заключение помечается «проверено не полностью». Заключение и лог разделов хранятся в сеансе и не "
           "пропадают после скачивания.",
           int((W - 2 * PX) / (16 * xl.CHAR_W)))
text_el(PX, y, _n8, 16, GRAY)
y += text_size(_n8, 16)[1] + 30
text_el(PX, y, "ЧЕРНОВИК КАРТОЧКИ СИСТЕМЫ — кнопка «Собрать черновик карточки системы по базе» в блоке "
               "«Для аудита» боковой панели (mint/cards.py)", 20, "#2f9e44")
y += 36
cards = [
    "draft_system_card()\nразделы карточки CARD_SECTIONS (10: названия, назначение, сервисы, лимиты, защита и "
    "хранение данных, планы, ограничения, подключение, требования) — параллельно, не больше CARD_PARALLEL и "
    "audit_parallel.",
    "ask_section()\nсвой запрос к поиску на раздел → search_parent_child(): CARD_TOP_K фрагментов, без multi-query; "
    "ничего не найдено — раздел пустой, без вызова LLM.",
    "ask_llm()\ncard_section_system: только по фрагментам, у каждого факта — [Источник: файл, раздел]; сведений "
    "нет — «НЕТ В БАЗЕ».",
    "check_citations()\nфакт без ссылки или со ссылкой мимо найденных фрагментов — пометка «⚠️ проверьте».",
    "card_markdown()\nкарточка по шаблону: «Названия:» (по ним аудит узнаёт систему в документе), пометка «черновик», "
    "разделы CARD_LAYOUT, пробелы «нет в базе», источники — source_name() без баллов поиска → скачать .md.",
    "Эксперт\nпроверяет факты по источникам, дописывает пробелы (ограничения, планы со сроками), убирает пометку → "
    "загружает карточку в базу → отмечает в «Карточки систем»: аудит берёт её в каждую проверку.",
]
cw = (W - 2 * PX - 5 * 30) / 6
c_els, ch = row_boxes(PX, y, [cw] * 6, cards, [("#2f9e44", "#ebfbee")] * 5 + [(DARK, "#f8f9fa")], gap=30, size=15,
                      text_color=DARK)
for a_, b_ in zip(c_els, c_els[1:]):
    arrow(a_, b_, "#2f9e44", a_side="right", b_side="left")
y += ch + 16
y = panel_end(p7, y)
y += 40


y += 40
# ======================================================================== 8. сервисы и нагрузка
p8 = y
y = panel_start(y, "9. Обращения к сервисам и нагрузка",
                "Для оценки мощностей шлюза под своё число пользователей и объём документов. Все сервисы — "
                "OpenAI-совместимый HTTP API.")
svc = [
    ("LLM — POST {LLM_API_URL}/chat/completions\n"
     "• ask_llm(): ответ в чате, condense_question(); в аудите — MAP, critique_findings(), глубокая проверка, пункты, "
     "merge_duplicate_findings(), select_summary(), compare_with_reference(); verify_remark() в контроле; "
     "draft_system_card() — вызов на раздел карточки; --generate в eval\n"
     "• expand_query_multi() — если use_multi_query\n"
     "• _llm_prompt_tokens() — измерение «символов на токен» (max_tokens = 1)\n"
     "• GET {LLM_API_URL}/models — detect_server_info(): список моделей и окна (панель 1)\n"
     "Повторы — llm_retries (панель 3); HTTP 429 — общая пауза всех потоков (_note_rate_limit(), Retry-After), "
     "_wait_rate_limit() перед каждым запросом."),
    ("Эмбеддинги — POST {EMBED_API_URL}\n"
     "• get_query_embedding(): вопрос, раздел документа в аудите, замечание в контроле\n"
     "• get_query_embeddings_batch(): индексация (пачками по embed_batch_size) и build_section_index()\n"
     "• в поиске до 3 попыток с паузой 2 с\n"
     "• GET …/models рядом с EMBED_API_URL — вход модели (панель 1)"),
    ("Реранкер — POST {RERANK_API_URL} (необязательно)\n"
     "• _rerank_request() через rerank_scores(): поиск и pick_sections_for_remark()\n"
     "• пачками (rerank_max_docs, rerank_char_budget)\n"
     "• повторов нет: ошибка → поиск без реранкера (в логе — HTTP-код и размер пачки)\n"
     "• probe_reranker() — проверка связи в панели (кэш 5 мин)\n"
     "Ответ: {results: [{index, relevance_score}]} или [{index, score}]."),
]
svw = (W - 2 * PX - 2 * 24) / 3
sv_styles = [("#f08c00", "#fff4e6"), ("#0c8599", "#e3fafc"), ("#e03131", "#fff5f5")]
_, svh = row_boxes(PX, y, [svw] * 3, svc, sv_styles, gap=24, size=FS, text_color=DARK)
y += svh + 30
load_rows = [
    ("Операция", "LLM", "Эмбеддинги", "Реранкер", "Что растёт с бизнес-объёмом"),
    ("Вопрос в чате", "1 (+1 уточнение при истории, +1 multi-query)", "1 (+1 multi-query)",
     "≈ 2 запроса (16 кандидатов пачками)", "число пользователей × вопросов в день"),
    ("Аудит документа, на раздел", "2 (MAP + самокритика) или 1; на аудит: +1 на пункт «особого внимания» и "
     "чек-листа, +1 на систему с карточкой, +1 "
     "сведение повторов, +1 «Главное», с оглавлением — сверка «не описано» (до 15); глубокая проверка — до "
     "audit_deep_max_calls; проходы 2–3 (audit_passes) повторяют разделы и вопросы о процессе и цифрах",
     "1 (+1 на аудит и +1 на пункт при «особом внимании»)", "≈ 2", "частей ≈ объём документа / audit_map_size: ФТ на "
     "20 тыс. симв. ≈ 6 частей ≈ 12 вызовов LLM + ≈ 35 коротких вопросов глубокой проверки (шагов процесса, "
     "требований и частей); документ целиком добавляет свой объём во вход каждой проверки раздела"),
    ("Контроль исправлений, на замечание", "1", "1 (+1 с нормами)", "≈ 1–2 (+2 с нормами)",
     "число замечаний; плюс эмбеддинги всех разделов новой редакции один раз"),
    ("Черновик карточки системы", "до 10 (раздел, по которому в базе ничего не нашлось, — без вызова)",
     "до 10 (поиск на раздел)", "≈ 2 на раздел", "число систем; разделы — параллельно, не больше 3"),
    ("Загрузка документа", "—", "child / embed_batch_size запросов", "—",
     "≈ 1 child на 250 симв. (400 − перекрытие 150): 250 тыс. симв. ≈ 1000 child ≈ 32 запроса"),
    ("Проверка качества (и eval_search.py)", "1 на вопрос при составлении вопросов; +1 с ответами чата или multi-query", "1 на вопрос", "≈ 2 на вопрос",
     "ответы кэшируются на все варианты настроек"),
]
lcw = [380, 430, 300, 330, W - 2 * PX - 380 - 430 - 300 - 330]
for k, row in enumerate(load_rows):
    style = (DARK, "#e9ecef") if k == 0 else (DARK, "#ffffff")
    _, rh = row_boxes(PX, y, lcw, list(row), style, gap=0, size=FS, text_color=DARK, min_h=30)
    y += rh
y += 24
mem = ("Память и диск (один процесс Streamlit на всех пользователей): FAISS IndexFlatL2 в памяти — child × "
       "размерность × 4 байта (Qwen3-Embedding-4B, 2560: ≈ 10 КБ на child, 10 000 child ≈ 100 МБ); BM25 — позиции "
       "слов всех parent; кэш _process_cache() держит базу одним экземпляром. Диск KB_DIR: индексы + оригиналы "
       "sources/. LOG_DIR: mint_system.log (до 60 МБ с ротацией) и feedback.jsonl — растёт с числом отзывов.")
mem_w = wrap(mem, int((W - 2 * PX) / (16 * xl.CHAR_W)))
text_el(PX, y, mem_w, 16, DARK)
y += text_size(mem_w, 16)[1] + 10
y = panel_end(p8, y)

# рамки панелей — под остальными элементами
for fr in reversed(frames):
    elements.insert(0, fr)
xl.save(elements, sys.argv[1], {"gridSize": 20, "viewBackgroundColor": "#ffffff", "currentItemFontFamily": 5,
                                "currentItemRoughness": 1, "currentItemStrokeColor": CODE})
print("элементов:", len(elements), "стрелок:", sum(e["type"] == "arrow" for e in elements),
      "высота:", round(y), "ширина:", W)
