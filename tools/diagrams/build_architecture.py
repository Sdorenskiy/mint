"""Генератор архитектурной схемы MINT в формате Excalidraw (.excalidraw и .excalidraw.md для Obsidian)."""
import json
import math
import random
import sys
import time

from lang import T

RND = random.Random(20261010)
B62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
NOW = int(time.time() * 1000)
FONT = 5            # Excalifont, как в образце
CHAR_W = 0.6        # оценка ширины символа (доля размера шрифта) для переноса строк
LINE_H = 1.25
PAD = 12

elements = []
_ids = set()


def new_id():
    while True:
        i = "".join(RND.choice(B62) for _ in range(8))
        if i not in _ids:
            _ids.add(i)
            return i


def frac_index(n):
    return "a" + B62[n] if n < 62 else "b" + B62[n // 62] + B62[n % 62]


def base(kind, x, y, w, h, stroke, bg="transparent", dashed=False, rounded=True, fill="solid", width=2):
    return {
        "id": new_id(), "type": kind, "x": round(x, 2), "y": round(y, 2), "width": round(w, 2), "height": round(h, 2),
        "angle": 0, "strokeColor": stroke, "backgroundColor": bg, "fillStyle": fill, "strokeWidth": width,
        "strokeStyle": "dashed" if dashed else "solid", "roughness": 1, "opacity": 100, "groupIds": [],
        "frameId": None, "roundness": {"type": 3} if rounded else None, "seed": RND.randint(1, 2 ** 31 - 1),
        "version": 1, "versionNonce": RND.randint(1, 2 ** 31 - 1), "isDeleted": False, "boundElements": [],
        "updated": NOW, "link": None, "locked": False,
    }


def wrap(text, max_chars):
    text = T(text)
    out = []
    for para in text.split("\n"):
        if not para.strip():
            out.append("")
            continue
        indent = len(para) - len(para.lstrip())
        words, line = para.split(" "), ""
        for wd in words:
            cand = (line + " " + wd) if line else wd
            if len(cand) <= max_chars or not line:
                line = cand
            else:
                out.append(line)
                line = " " * (indent + 3 if para.lstrip()[:2] in ("• ", "- ") or para.lstrip()[:1].isdigit() else indent) + wd
        out.append(line)
    return "\n".join(out)


def text_size(text, size):
    text = T(text)
    lines = text.split("\n")
    return max(len(l) for l in lines) * size * CHAR_W, len(lines) * size * LINE_H


def text_el(x, y, text, size=20, color="#1e1e1e", align="left", valign="top", container=None, w=None, h=None):
    text = T(text)
    tw, th = text_size(text, size)
    el = base("text", x, y, w if w is not None else tw, h if h is not None else th, color, rounded=False)
    el.update({"text": text, "fontSize": size, "fontFamily": FONT, "textAlign": align, "verticalAlign": valign,
               "containerId": container["id"] if container else None, "originalText": text, "autoResize": True,
               "lineHeight": LINE_H})
    elements.append(el)
    if container is not None:
        container["boundElements"].append({"type": "text", "id": el["id"]})
    return el


def box(x, y, w, h, text="", stroke="#1e1e1e", bg="transparent", size=18, align="center", valign="middle",
        dashed=False, text_color=None, kind="rectangle"):
    el = base(kind, x, y, w, h, stroke, bg, dashed=dashed)
    elements.append(el)
    if text:
        wrapped = wrap(text, max(8, int((w - 2 * PAD) / (size * CHAR_W))))
        tw, th = text_size(wrapped, size)
        tw = min(tw, w - 2 * PAD)
        tx = x + (w - tw) / 2 if align == "center" else x + PAD
        ty = y + (h - th) / 2 if valign == "middle" else y + PAD
        text_el(tx, ty, wrapped, size, text_color or stroke, align, valign, container=el, w=tw, h=th)
    return el


def needed_height(text, w, size, extra=2 * PAD):
    wrapped = wrap(text, max(8, int((w - 2 * PAD) / (size * CHAR_W))))
    return text_size(wrapped, size)[1] + extra


def anchor(el, side, t=0.5):
    """Точка на стороне элемента: side ∈ top/bottom/left/right, t — доля вдоль стороны."""
    x, y, w, h = el["x"], el["y"], el["width"], el["height"]
    return {"top": (x + w * t, y), "bottom": (x + w * t, y + h), "left": (x, y + h * t),
            "right": (x + w, y + h * t)}[side]


def _binding(el, px, py):
    fx = (px - el["x"]) / el["width"] if el["width"] else 0.5
    fy = (py - el["y"]) / el["height"] if el["height"] else 0.5
    return {"elementId": el["id"], "focus": 0, "gap": 8, "mode": "orbit",
            "fixedPoint": [round(min(1, max(0, fx)), 4), round(min(1, max(0, fy)), 4)]}


def arrow(a, b, color, label=None, both=False, dashed=False, a_side="bottom", b_side="top", a_t=0.5, b_t=0.5,
          via=None, label_size=16):
    sx, sy = anchor(a, a_side, a_t)
    ex, ey = anchor(b, b_side, b_t)
    gap = 6
    dirs = {"top": (0, -1), "bottom": (0, 1), "left": (-1, 0), "right": (1, 0)}
    sx += dirs[a_side][0] * gap; sy += dirs[a_side][1] * gap
    ex += dirs[b_side][0] * gap; ey += dirs[b_side][1] * gap
    pts = [(sx, sy)] + list(via or []) + [(ex, ey)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    el = base("arrow", sx, sy, max(xs) - min(xs), max(ys) - min(ys), color, dashed=dashed, rounded=False)
    el["roundness"] = {"type": 2}
    el.update({"points": [[round(px - sx, 2), round(py - sy, 2)] for px, py in pts], "lastCommittedPoint": None,
               "startBinding": _binding(a, *anchor(a, a_side, a_t)), "endBinding": _binding(b, *anchor(b, b_side, b_t)),
               "startArrowhead": "arrow" if both else None, "endArrowhead": "arrow", "elbowed": False})
    elements.append(el)
    a["boundElements"].append({"type": "arrow", "id": el["id"]})
    b["boundElements"].append({"type": "arrow", "id": el["id"]})
    if label:
        mid = len(pts) // 2
        (x1, y1), (x2, y2) = pts[mid - 1], pts[mid]
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        tw, th = text_size(label, label_size)
        text_el(mx - tw / 2, my - th / 2, label, label_size, color, "center", "middle", container=el, w=tw, h=th)
    return el


# ---------------------------------------------------------------- палитра (как в образце + стандартная Excalidraw)
GREEN, GREEN_BG, GREEN_TAB = "#2f9e44", "#ebfbee", "#b2f2bb"
ORANGE, ORANGE_BG, ORANGE_TAB = "#f08c00", "#fff4e6", "#ffec99"
BLUE, BLUE_BG, BLUE_TAB = "#1971c2", "#e7f5ff", "#a5d8ff"
VIOLET, VIOLET_BG, VIOLET_TAB = "#6741d9", "#f3f0ff", "#d0bfff"
CYAN, CYAN_BG = "#0c8599", "#e3fafc"
DARK, GRAY, GRAY_BG = "#1e1e1e", "#868e96", "#f8f9fa"
FRAME = "#95779c"
STORE_BG, EXT_BG = "#ffec99", "#ffc9c9"

COL_W, GAP = 380, 30
COLS = [i * (COL_W + GAP) for i in range(4)]
RIGHT = COLS[-1] + COL_W

# ================================================================ Панель 1: общая схема
text_el(0, 0, "MINT — архитектура решения", 36, DARK)
text_el(0, 54, "Интеллектуальная RAG-система: чат по базе знаний, аудит документов и контроль исправления замечаний. "
              "Python + Streamlit, пакет mint/; русский и английский", 18, GRAY)
ARROW_T = 0.82   # вертикальные связи «вход → вкладка → сценарий» — в правой части колонки, мимо подписей областей

flows = [
    ("Документы для базы (.docx, .pdf, .md, .txt): регламенты, стандарты", GREEN),
    ("Вопрос пользователя", ORANGE),
    ("Документ на согласование (.docx, .pdf, .md, .txt), критерии и «особое внимание»", BLUE),
    ("Выданные замечания и новая редакция документа (.docx, .pdf, .md, .txt)", VIOLET),
]
inputs = [box(COLS[i], 110, COL_W, 74, t, c, size=18) for i, (t, c) in enumerate(flows)]

tabs_txt = [("Боковая панель: документы базы, настройки, модели и лимиты, сокращения, правила экспертов и карточки "
             "систем (черновик карточки — по базе), проверка качества, промпты, язык RU / EN, отзывы",
             GREEN, GREEN_TAB),
            ("Вкладка «Чат»", ORANGE, ORANGE_TAB),
            ("Вкладка «Аудит документа»: документ, критерии, «особое внимание», ⚙️ настройки аудита в одном блоке, "
             "«Мои аудиты»",
             BLUE, BLUE_TAB),
            ("Вкладка «Контроль исправлений»", VIOLET, VIOLET_TAB)]
TAB_H = max([104] + [needed_height(t, COL_W, 17) for t, _c, _b in tabs_txt])
ui = box(-20, 240, RIGHT + 40, TAB_H + 72, "", DARK, GRAY_BG)
text_el(0, 250, "Интерфейс — Streamlit", 20, DARK)
tabs = [box(COLS[i], 290, COL_W, TAB_H, t, c, bg, size=17) for i, (t, c, bg) in enumerate(tabs_txt)]
for i in range(4):
    arrow(inputs[i], tabs[i], flows[i][1], a_t=ARROW_T, b_t=ARROW_T)

flow_texts = [
    ("ДОБАВЛЕНИЕ ДОКУМЕНТОВ В БАЗУ",
     "1. Разбор: .docx — Docling; .pdf — без моделей (заголовки из закладок, оглавления, по шрифту); .md, .txt "
     "→ текст, заголовки, таблицы\n"
     "2. Нарезка по границам абзацев и предложений: parent 2500 симв. для LLM, child 400 симв. для поиска; "
     "таблицы — по строкам\n"
     "3. Эмбеддинги child (вместе с путём заголовков)\n"
     "4. Запись в хранилище: векторы, фрагменты, индекс слов\n"
     "5. Автосбор сокращений из документов; в манифест — модель и параметры нарезки\n"
     "6. Черновик карточки системы (по кнопке на боковой панели): по каждому разделу карточки — поиск по базе и "
     "ответ LLM только по найденному, у каждого факта — источник, чего нет — «нет в базе»; эксперт проверяет, "
     "дописывает и загружает карточку в базу"),
    ("ЧАТ ПО БАЗЕ ЗНАНИЙ",
     "1. Уточняющий вопрос переписывается в самостоятельный по истории диалога\n"
     "2. Поиск по базе → 4–5 лучших фрагментов\n"
     "3. Контекст: фрагменты с файлом и разделами (соседние — одним блоком, длинные — вокруг найденного места) "
     "+ справочник сокращений\n"
     "4. LLM отвечает только по контексту\n"
     "5. Ответ со ссылками [файл, раздел] и списком источников; ссылки сверяются с найденными фрагментами, "
     "неверные помечены ⚠; отзыв: оценка и комментарий"),
    ("АУДИТ ДОКУМЕНТА (MAP → REDUCE)",
     "1. Разбор документа → .md → части по разделам до 4500 симв. (раздел с таблицей — целиком); для сравнения — "
     "весь документ одним запросом\n"
     "2. MAP: каждая часть — с нормами из базы, документами-основаниями (по ссылкам документа на них), правилами "
     "экспертов, карточками упомянутых систем и документом "
     "целиком для справки (не помещается в окно — с оглавлением) → LLM пишет замечания; описанный процесс — по "
     "шагам; по желанию — с рассуждениями модели\n"
     "3. Самокритика (можно выключить): оставить или удалить, критичность, дословная цитата; замечание о пункте "
     "другой части отсеивается\n"
     "4. Глубокая проверка: узкие вопросы — каждая пара шагов процесса, каждое требование, границы; противоречия "
     "между разделами; цифры (считает программа); опечатки\n"
     "5. Проходы 2–3 (по желанию): разделы и вопросы о процессе и цифрах — ещё раз с температурой ≥ 0,4; "
     "найденное несколькими проходами — выше\n"
     "6. «Особое внимание» и чек-лист по типу документа — ответ на каждый пункт по всему документу вместе с "
     "замечаниями, уже найденными другими проверками; что документ требует от каждой упомянутой системы\n"
     "7. Без модели: сокращения, оформление; ссылки и цифры из замечаний сверяются с документом и нормами\n"
     "8. REDUCE: повторы — по словам (в кусках одной длинной таблицы — мягче) и моделью (замечания о разных шагах "
     "процесса не сливаются); замечания — по "
     "разделам документа, в его порядке; «Главное» — модель-редактор выбирает самые важные\n"
     "9. Заключение .md, документ с примечаниями Word, лог проверки и сырые ответы модели .md; сверка с эталоном; "
     "отзыв: оценка и комментарий\n"
     "10. Аудит сохраняется (LOG_DIR/audits) и открывается позже; эксперт размечает замечания («беру» / «мелочь» / "
     "«неверно» с причиной) и дописывает свои → «Мои замечания» Word / .md и файл разбора для улучшения MINT"),
    ("КОНТРОЛЬ ИСПРАВЛЕНИЙ",
     "1. Новая редакция документа → разделы\n"
     "2. Для каждого замечания — подходящие разделы (вектор + слова + реранкер) и, по желанию, нормы из базы\n"
     "3. LLM: статус «исправлено / частично / нет» и дословная цитата\n"
     "4. Цитата сверяется с текстом редакции\n"
     "5. Матрица контроля .md / .docx; отзыв: оценка и комментарий"),
]
core_top = 240 + TAB_H + 72 + 40
FLOW_Y, FS = core_top + 54, 17
flow_bodies = [f"{title}\n\n{body}" for title, body in flow_texts]
FLOW_H = max(needed_height(t, COL_W, FS) for t in flow_bodies) + 10
flows_el = []
for i, txt in enumerate(flow_bodies):
    color, bg = [(GREEN, GREEN_BG), (ORANGE, ORANGE_BG), (BLUE, BLUE_BG), (VIOLET, VIOLET_BG)][i]
    flows_el.append(box(COLS[i], FLOW_Y, COL_W, FLOW_H, txt, color, bg, size=FS, align="left", valign="top"))
for i in range(4):
    arrow(tabs[i], flows_el[i], flows_el[i]["strokeColor"], both=True, a_t=ARROW_T, b_t=ARROW_T)

ENG_Y = FLOW_Y + FLOW_H + 70
eng_text = ("Поисковый движок (общий для чата, аудита и контроля исправлений)\n"
            "вектор (FAISS, смысл) + слова (BM25: основы русских и английских слов, расшифровки сокращений) → "
            "слияние рангов (RRF) → реранкер (необязательно) → лучшие фрагменты + сигнал «уверенность низкая». "
            "Подробно — на схеме ниже.")
ENG_W = RIGHT - COLS[1]
ENG_H = needed_height(eng_text, ENG_W, 18) + 6
engine = box(COLS[1], ENG_Y, ENG_W, ENG_H, eng_text, CYAN, CYAN_BG, size=18, align="left", valign="top")
for i in (1, 2, 3):   # контроль исправлений берёт нормы из базы по желанию — пунктир
    arrow(flows_el[i], engine, flows_el[i]["strokeColor"], dashed=(i == 3),
          b_t=(COLS[i] + COL_W / 2 - COLS[1]) / ENG_W)
# черновик карточки системы ищет по базе — по кнопке, пунктир
arrow(flows_el[0], engine, GREEN, dashed=True, label="черновик карточки", a_t=0.85, b_side="left",
      via=[(COLS[0] + COL_W * 0.85, ENG_Y + ENG_H / 2)])

core_bottom = ENG_Y + ENG_H + 30
core = base("rectangle", -20, core_top, RIGHT + 40, core_bottom - core_top, BLUE, "transparent")
elements.insert(0, core)       # рамка ядра — под остальными элементами
text_el(0, core_top + 12, "Ядро MINT — Python", 20, BLUE)
ui_el = ui
elements.remove(ui_el)
elements.insert(0, ui_el)

# ---------------- хранилище и внешние сервисы
ST_Y = core_bottom + 80
store_items = [
    "FAISS — векторы child (по ним ищет «вектор»)",
    "parent_store.json — фрагменты parent (их читает LLM)",
    "bm25_index.pkl — индекс слов по основам",
    "auto_glossary.json — сокращения из документов",
    "manifest.json — модель эмбеддингов и нарезка каждого документа; audit_roles.json — правила экспертов и "
    "карточки систем для аудита",
    "sources/ — оригиналы документов для переиндексации",
]
ST_W = COLS[2] + COL_W - 0
item_w = (ST_W - 2 * 20 - 2 * 20) / 3
item_h = max(needed_height(t, item_w, 16) for t in store_items) + 4
store = base("rectangle", 0, ST_Y, ST_W, 70 + 2 * item_h + 20 + 20, DARK, STORE_BG, dashed=True)
elements.append(store)
text_el(20, ST_Y + 12, "Хранилище базы знаний — папка KB_DIR на машине", 22, DARK)
for k, t in enumerate(store_items):
    r, c = divmod(k, 3)
    box(20 + c * (item_w + 20), ST_Y + 56 + r * (item_h + 16), item_w, item_h, t, DARK, "#fff9db", size=16)

EXT_X = COLS[3]
ext_items = [("LLM — ответы, замечания, самокритика, «Главное», черновики карточек", False),
             ("Модель эмбеддингов — векторы", False),
             ("Реранкер — оценка релевантности (необязательно)", True)]
ext = base("rectangle", EXT_X, ST_Y, COL_W, store["height"], DARK, EXT_BG)
elements.append(ext)
text_el(EXT_X + 16, ST_Y + 12, "Внешние сервисы", 22, DARK)
text_el(EXT_X + 16, ST_Y + 42, "любой OpenAI-совместимый API", 16, DARK)
ext_h = (store["height"] - 80 - 2 * 12 - 16) / 3
ext_boxes = [box(EXT_X + 16, ST_Y + 76 + k * (ext_h + 12), COL_W - 32, ext_h, t, DARK, "#ffe3e3", size=16, dashed=d)
             for k, (t, d) in enumerate(ext_items)]

arrow(flows_el[0], store, GREEN, label="запись", b_t=(COLS[0] + COL_W / 2) / ST_W)
arrow(engine, store, CYAN, label="чтение", a_t=(COLS[1] + COL_W / 2 - COLS[1]) / ENG_W,
      b_t=(COLS[1] + COL_W / 2) / ST_W)
arrow(core, ext, DARK, label="HTTP", a_t=(EXT_X + COL_W / 2 + 20) / core["width"], b_t=0.5)

# ---------------- подвал: настройки, размеры, оценка
FT_Y = ST_Y + store["height"] + 50
foot_w = (RIGHT - 2 * 30) / 3
foot = [
    ("Настройки\n"
     "• .env — адреса API, ключи, модели, папки, язык (MINT_LANG)\n"
     "• config.yaml — параметры поиска и аудита (необязательно)\n"
     "• glossary.json — свои расшифровки сокращений (необязательно)\n"
     "• checklists.yaml — свои чек-листы аудита по типам документов (образец — checklists.example.yaml; файл вне "
     "папки программы — путь в MINT_CHECKLISTS)\n"
     "• mint/prompts/ru.yaml, en.yaml — тексты промптов по умолчанию; свои правки — prompts.yaml (страница "
     "«Промпты»); версия набора пишется в отзывы, лог аудита и проверку качества\n"
     "• боковая панель — изменения на время сеанса\n"
     "• LOG_DIR — журнал работы, отзывы пользователей (feedback.jsonl), проверки качества (eval/), сохранённые "
     "аудиты с разбором экспертов (audits/)", GRAY),
    ("Размеры по умолчанию (MINT подстраивает их под лимиты моделей)\n"
     "• parent 2500 симв. ≈ 1–1,5 страницы — уходит в контекст LLM\n"
     "• child 400 симв. ≈ 2–3 предложения — единица векторного поиска\n"
     "• раздел документа в аудите 4500 симв. ≈ 3–4 страницы\n"
     "• фрагмент для реранкера 800 симв.", GRAY),
    ("Проверка и оценка качества\n"
     "• check_install.py — самопроверка установки: пакеты, разбор .docx и .pdf, подключения к моделям, страница\n"
     "• «Проверка качества» на боковой панели (в консоли — eval_search.py) — вопросы по базе через поиск в "
     "нескольких вариантах (вектор, слова, гибрид, гибрид + реранкер): hit@k, MRR, случайна ли разница, порог "
     "«уверенность низкая», рекомендации; по желанию — ответы чата: ошибка поиска или модели, сравнение по версии "
     "промптов\n"
     "• разборы замечаний экспертами (файлы разбора) — tools/review_stats.py: доля верных замечаний по видам "
     "проверок, причины ошибок, что MINT пропустил\n"
     "• tests/ — автотесты без сети и моделей, GitHub Actions", GRAY),
]
FT_H = max(needed_height(t, foot_w, 16) for t, _ in foot)
for k, (t, c) in enumerate(foot):
    box(k * (foot_w + 30), FT_Y, foot_w, FT_H, t, c, GRAY_BG, size=16, align="left", valign="top", text_color=DARK)

top_frame = base("rectangle", -50, -30, RIGHT + 100, FT_Y + FT_H + 40 + 30, FRAME, "transparent")
elements.insert(0, top_frame)

# ================================================================ Панель 2: поиск подробно
P_Y = FT_Y + FT_H + 140
text_el(0, P_Y, "Поиск по базе — как находится нужный фрагмент", 30, DARK)
text_el(0, P_Y + 46, "Шаги 1–5 общие для чата, аудита и контроля исправлений; шаги 6–7 — ответ в чате.", 18, GRAY)
STEP_W, STEP_GAP = 200, 35
steps = [
    ("1. Вопрос", "в чате уточнение переписывается по истории диалога", CYAN, CYAN_BG, False),
    ("2а. Вектор (смысл)", "эмбеддинг вопроса (с инструкцией, если её требует модель) → FAISS → 50 ближайших "
                           "child → их parent",
     CYAN, CYAN_BG, False),
    ("2б. Слова (BM25)", "основы слов (русских и английских) + расшифровки сокращений → 20 лучших parent",
     CYAN, CYAN_BG, False),
    ("3. Слияние рангов (RRF)", "16 кандидатов; найденные обоими каналами — выше", CYAN, CYAN_BG, False),
    ("4. Реранкер", "необязательно: оценивает все 16 по самому релевантному фрагменту (≤ 800 симв.); "
                    "его голос добавляется к слиянию", CYAN, CYAN_BG, True),
    ("5. Отбор 4–5 фрагментов", "без повторов, не больше 2 частей одной таблицы; сигнал «уверенность низкая» — "
                                "по баллу реранкера, без него — по словам вопроса",
     CYAN, CYAN_BG, False),
    ("6. Контекст для LLM", "фрагменты parent с файлом и разделами: соседние — одним блоком, длинные — вокруг "
                            "найденного места; + справочник сокращений", ORANGE, ORANGE_BG, False),
    ("7. Ответ", "только по контексту, со ссылками [файл, раздел]; ссылки сверяются с контекстом; нет ответа в "
                 "базе — так и говорит",
     ORANGE, ORANGE_BG, False),
]
SF = 16
step_txt = [f"{t}\n\n{d}" for t, d, *_ in steps]
H_half = max(needed_height(step_txt[i], STEP_W, SF) for i in (1, 2))
H_full = max(max(needed_height(step_txt[i], STEP_W, SF) for i in (0, 3, 4, 5, 6, 7)), 2 * H_half + 24)
ROW_Y = P_Y + 100
xs = [k * (STEP_W + STEP_GAP) for k in range(7)]
s_el = {}
s_el[0] = box(xs[0], ROW_Y, STEP_W, H_full, step_txt[0], *steps[0][2:4], size=SF, dashed=steps[0][4])
s_el[1] = box(xs[1], ROW_Y, STEP_W, H_half, step_txt[1], *steps[1][2:4], size=SF)
s_el[2] = box(xs[1], ROW_Y + H_full - H_half, STEP_W, H_half, step_txt[2], *steps[2][2:4], size=SF)
for k, si in ((2, 3), (3, 4), (4, 5), (5, 6), (6, 7)):
    s_el[si] = box(xs[k], ROW_Y, STEP_W, H_full, step_txt[si], *steps[si][2:4], size=SF, dashed=steps[si][4])
arrow(s_el[0], s_el[1], CYAN, a_side="right", b_side="left", a_t=0.3)
arrow(s_el[0], s_el[2], CYAN, a_side="right", b_side="left", a_t=0.7)
arrow(s_el[1], s_el[3], CYAN, a_side="right", b_side="left", b_t=0.3)
arrow(s_el[2], s_el[3], CYAN, a_side="right", b_side="left", b_t=0.7)
for a_, b_, c_ in ((3, 4, CYAN), (4, 5, CYAN), (5, 6, ORANGE), (6, 7, ORANGE)):
    arrow(s_el[a_], s_el[b_], c_, a_side="right", b_side="left")
note2 = ("Если сервис эмбеддингов недоступен, работает только канал «Слова». Реранкер с пунктирной рамкой — "
         "необязательный: без него поиск идёт по шагам 1–3 и 5.")
text_el(0, ROW_Y + H_full + 24, note2, 16, GRAY)
p_frame = base("rectangle", -50, P_Y - 30, RIGHT + 100, (ROW_Y + H_full + 24 + 40) - (P_Y - 30), FRAME, "transparent")
elements.insert(0, p_frame)

# ---------------------------------------------------------------- сохранение
for n, el in enumerate(elements):
    el["index"] = frac_index(n)

scene = {"type": "excalidraw", "version": 2, "source": "https://excalidraw.com", "elements": elements,
         "appState": {"gridSize": 20, "viewBackgroundColor": "#ffffff", "currentItemFontFamily": FONT,
                      "currentItemRoughness": 1, "currentItemStrokeColor": BLUE},
         "files": {}}
out = sys.argv[1]
with open(out + ".excalidraw", "w", encoding="utf-8") as f:
    json.dump(scene, f, ensure_ascii=False, indent=2)

texts = [e for e in elements if e["type"] == "text"]
md = ["---", "", "excalidraw-plugin: parsed", "tags: [excalidraw]", "", "---",
      "==⚠  Switch to EXCALIDRAW VIEW in the MORE OPTIONS menu of this document. ⚠== You can decompress Drawing "
      "data with the command palette: 'Decompress current Excalidraw file'. For more info check in plugin settings "
      "under 'Saving'", "", "", "# Excalidraw Data", "", "## Text Elements"]
for t in texts:
    md += [f"{t['text']} ^{t['id']}", ""]
md += ["%%", "## Drawing", "```json", json.dumps(scene, ensure_ascii=False, indent=2), "```", "%%"]
with open(out + ".excalidraw.md", "w", encoding="utf-8") as f:
    f.write("\n".join(md) + "\n")
print(f"элементов: {len(elements)}, стрелок: {sum(e['type'] == 'arrow' for e in elements)}, "
      f"текстов: {len(texts)}")
