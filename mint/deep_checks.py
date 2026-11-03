"""Глубокая проверка аудита: вместо одной большой просьбы к модели — много узких вопросов, на которые надёжно
отвечает и модель среднего размера, и проверки кодом.

Сильная модель находит разрыв между шагами процесса или противоречие между разделами «сама»; модели на 20–30
млрд параметров на это не хватает, если вопрос — «проведи аудит главы». Поэтому то, что делает внимательный
эксперт, разложено на задачи:

- процесс: код находит таблицы операций, списки шагов и подразделы «Шаг N»; модель отвечает на вопросы по
  каждой паре соседних шагов (откуда вход, кто передаёт, может ли получатель прочитать данные), по каждому
  требованию к процессу (есть ли шаг, нет ли противоречия) и по границам процесса (начало, конец, результат
  каждому потребителю);
- противоречия между разделами: модель выписывает из каждой части утверждения с темой из закрытого списка, код
  группирует их по темам, модель сравнивает утверждения одной темы;
- цифры: код выписывает показатели с единицами и сам считает (сутки × 365 против года), модель оценивает;
- опечатки: короткий проход модели по каждой части;
- оформление (без модели): пункт, оформленный текстом вместо заголовка, расхождение содержания с заголовками,
  пустые таблицы, колонки и поля, пустые разделы.

Задачи модели выполняются параллельно (audit_parallel запросов одновременно), их число ограничено
audit_deep_max_calls.
"""

import re
import time

from .i18n import tr
from .parallel import parallel_map
from .prompts import prompt_text, render
from .sections import section_label
from .services import ask_llm
from .text import extract_json

# ---------------------------------------------------------------- таблицы Markdown

_SEP_CELL_RE = re.compile(r"\s*:?-{2,}:?\s*")


def _plain_cell(c):
    """«**Исполнитель**» → «Исполнитель»: ячейка, целиком выделенная жирным (шапки таблиц из Word)."""
    for mark in ("**", "__"):
        if len(c) > 4 and c.startswith(mark) and c.endswith(mark) and mark not in c[2:-2]:
            return c[2:-2].strip()
    return c


def table_rows(text):
    """Таблица Markdown → (шапка, строки) — ячейки без пробелов по краям; строка-разделитель пропускается."""
    rows = []
    for line in (text or "").split("\n"):
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [_plain_cell(c.strip()) for c in re.split(r"(?<!\\)\|", s.strip("|"))]
        if cells and all(_SEP_CELL_RE.fullmatch(c) for c in cells if c) and any(cells):
            continue
        rows.append(cells)
    if not rows:
        return [], []
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    return rows[0], rows[1:]


def _is_table(text):
    lines = [ln for ln in (text or "").split("\n") if ln.strip()]
    return len(lines) >= 2 and all(ln.lstrip().startswith("|") for ln in lines)


def _filled(row):
    return sum(1 for c in row if c)


# ---------------------------------------------------------------- процесс: таблицы операций

_PROCESS_COL_RE = re.compile(r"(?i)операци|шаг|этап|действи|исполнител|участник|входн|результат|выходн|сервис|систем|"
                             r"operation|step|stage|action|actor|performer|input|output|result|service|system")
_STEP_NO_RE = re.compile(r"^\d+(?:\.\d+)*\.?$")
_INFO_KEY_RE = re.compile(r"(?i)границ|участник|результат|потребител|поставщик|boundar|participant|result|consumer|supplier")
_REQ_TITLE_RE = re.compile(r"(?i)требовани|requirement")


def find_process_tables(blocks):
    """Таблицы операций процесса: в шапке не меньше трёх колонок вида «операция / исполнитель / входные данные /
    результат / сервис» и не меньше трёх заполненных строк. → [{index, path, header, rows}]."""
    out = []
    for i, b in enumerate(blocks):
        if b["level"] or not _is_table(b["text"]):
            continue
        header, rows = table_rows(b["text"])
        rows = [r for r in rows if _filled(r) >= 2]
        if sum(1 for c in header if _PROCESS_COL_RE.search(c)) >= 3 and len(rows) >= 3:
            out.append({"index": i, "path": b["path"], "header": header, "rows": rows})
    return out


def _step_no(row, i):
    return row[0].rstrip(".") if row and _STEP_NO_RE.match(row[0] or "") else str(i + 1)


def step_text(header, row, i):
    """Шаг таблицы одной строкой: «Шаг 4: Операция: …; Исполнитель: …; …»."""
    cols = list(zip(header, row))
    if row and _STEP_NO_RE.match(row[0] or ""):
        cols = cols[1:]
    body = "; ".join(f"{h or '—'}: {c}" for h, c in cols if c)
    return tr("Шаг {n}: {body}", n=_step_no(row, i), body=body)


# «- **Срок хранения:** 5 лет»: название начинается не с пробела — иначе на строке из пробелов разбор перебирал бы,
# какие из них отдать «\s*», а какие названию
_INFO_LINE_RE = re.compile(r"^\s*(?:[-–—•·*]\s+)?(?:[*_]+\s*)?([^:\s*_][^:\n]{2,79}?)[*_]*\s*:\s*(\S.{5,})$")


def process_info(blocks, table):
    """Сведения о процессе для вопросов модели: строки таблиц «границы / участники / результаты» (у процесса без
    таблицы — и такие же строки текстом «Участники процесса: …» в его разделе) и требования к процессу — абзацы
    после таблицы (списка шагов) в том же разделе и разделы «Требования…» рядом с ним. table — описание процесса
    из find_process_tables() или find_processes(): index — последний его блок, path — раздел."""
    info, reqs = [], []
    for b in blocks:
        if b["level"] or not _is_table(b["text"]):
            continue
        header, rows = table_rows(b["text"])
        for r in [header] + rows:
            cells = [c for c in r if c]
            if len(cells) >= 2 and _INFO_KEY_RE.search(cells[0]) and len(cells[0]) <= 80:
                info.append(f"{cells[0]}: {' '.join(cells[1:])}")
    parent = table["path"].rsplit(" → ", 1)[0] if " → " in table["path"] else ""
    area = parent or table["path"]
    for j, b in enumerate(blocks):
        if b["level"] or _is_table(b["text"]):
            continue
        # «Участники процесса: …» текстом в разделе процесса — для процесса без таблицы (у таблицы операций
        # сведения, как и раньше, из таблиц: вопросы по ней не меняются)
        if table.get("kind", "table") != "table" and area and (b["path"] == area or b["path"].startswith(area + " → ")):
            for line in b["text"].split("\n"):
                m = _INFO_LINE_RE.match(line.lstrip()) if ":" in line else None    # без ведущих пробелов: не перебирать их
                if m and _INFO_KEY_RE.search(m.group(1)) and not _STEP_WORD_RE.match(m.group(1)):
                    info.append(f"{m.group(1).strip()}: {m.group(2).strip()}")
        same = j > table["index"] and b["path"] == table["path"]
        last = b["path"].split(" → ")[-1]
        sibling = (parent and b["path"].startswith(parent + " → ") and b["path"] != table["path"]
                   and _REQ_TITLE_RE.search(last))
        if same or sibling:
            for line in b["text"].split("\n"):
                line = line.strip()
                if len(line) < 25 or (len(line) < 70 and _REQ_TITLE_RE.search(line) and _HEAD_NO_RE.match(line)):
                    continue                     # «2.2.4. Требования к процессу.» — заголовок, а не требование
                reqs.append(line)
    return list(dict.fromkeys(info)), reqs


# ---------------------------------------------------------------- процесс: списки шагов и разделы «Шаг N»
#
# Процесс описывают не только таблицей операций: нумерованным списком («1. Поставщик формирует файл…»), абзацами
# «Шаг 1. …» или подразделами «2.2.1 Шаг 1. Формирование файла». Чтобы не принять за процесс любой список, нужен
# признак процесса: слово «Шаг / Этап» у пунктов, или слова «порядок», «последовательность», «сценарий» … в
# названии раздела или во вводной фразе перед списком; списки требований, участников, терминов и документов — не
# процесс.

_STEP_WORD_RE = re.compile(r"(?i)^(?:шаг|этап|step|stage)\s*(\d{1,2})\b[.:)]?\s*[—–-]?\s*")
_ITEM_RE = re.compile(r"^(\s*)(?:([-–—•·*+])|(\d{1,2})[.)]|(?:шаг|этап|step|stage)\s*(\d{1,2})[.:)]?)\s+(\S.*)$",
                      re.IGNORECASE)
_PROCESS_STRONG_RE = re.compile(r"(?i)порядок|последовательност|алгоритм|сценари|этап|\bшаг|ход\s+(?:процесс|работ)|"
                                r"процесс\w*\s+(?:включает|состоит|выполняется|проходит|предусматривает)|"
                                r"workflow|procedure|sequence|scenario|\bsteps?\b|\bstages?\b")
_PROCESS_WEAK_RE = re.compile(r"(?i)процесс|взаимодейств|process|interaction|\bflow\b")
# список требований, терминов, содержание — не процесс, как бы он ни был назван
_NOT_PROCESS_RE = re.compile(r"(?i)требовани|термин|определени|сокращени|содержани|оглавлени|requirement|\bterms?\b|"
                             r"definition|abbreviation|contents")
# список участников, ролей, документов — не процесс, если рядом нет слов «порядок», «шаги» …
_LIST_OF_RE = re.compile(r"(?i)участник|\bрол[ьиея]|перечень|нормативн|ссылк|participant|\broles?\b|reference")
_MODAL_RE = re.compile(r"(?i)\bдолж(?:ен|на|но|ны)\b|\bнеобходимо\b|\bтребуется\b|не допускается|\bmust\b|\bshall\b|"
                       r"\bshould\b")
LIST_STEPS_MIN = 3          # пунктов в списке шагов — не меньше
STEP_CHARS_MAX = 700        # текст одного шага в вопросе модели
TEXT_PROCESSES_MAX = 5      # процессов, описанных списком или разделами, на документ


def _item(line):
    """Пункт списка → (отступ, вид, номер, текст) или None. Вид: bullet («- …»), number («1. …», «1) …»), step
    («Шаг 1. …», «- Этап 2: …»)."""
    m = _ITEM_RE.match(line)
    if not m:
        return None
    kind, no, text = ("step", m.group(4), m.group(5)) if m.group(4) else \
        ("number", m.group(3), m.group(5)) if m.group(3) else ("bullet", "", m.group(5))
    s = _STEP_WORD_RE.match(text)
    if s and kind != "step":                     # «- Шаг 1. …», «1. Этап 1: …»
        kind, no, text = "step", s.group(1), text[s.end():]
    return len(m.group(1).expandtabs(4)), kind, no, text.strip().lstrip("—–-: ").strip()


def _list_items(blocks, start, end):
    """Списки внутри одного раздела (блоки start…end-1): [{items: [{no, text}], kind, first, last, lead}]. Пункт —
    строка со знаком списка, номером «1.» / «1)» или «Шаг 1»; строки с отступом — подпункты и перенос строки пункта,
    строка без знака в том же абзаце — тоже продолжение пункта; абзац без знака списка заканчивает список. lead —
    вводная фраза перед списком."""
    lists, cur, lead = [], None, ""

    def close():
        nonlocal cur
        if cur and cur["items"]:
            lists.append(cur)
        cur = None

    for j in range(start, end):
        if _is_table(blocks[j]["text"]):
            close()
            lead = ""
            continue
        for line in blocks[j]["text"].split("\n"):
            if not line.strip():
                continue
            it = _item(line)
            indent = it[0] if it else len(line) - len(line.lstrip())
            if it and indent <= 1:
                if cur and cur["kind"] != it[1]:
                    close()
                if cur is None:
                    cur = {"items": [], "kind": it[1], "first": j, "last": j, "lead": lead}
                cur["items"].append({"no": it[2], "text": it[3]})
                cur["last"] = j
            elif cur and (indent >= 2 or j == cur["last"]):
                # подпункт — через «; », перенос строки пункта (Markdown с переносами) — через пробел
                cur["items"][-1]["text"] += ("; " + it[3]) if it else (" " + line.strip())
                cur["last"] = j
            else:
                close()
                lead = line.strip()
    close()
    return lists


def _is_process_list(lst, title):
    """Список — шаги процесса? Не меньше LIST_STEPS_MIN пунктов длиной в предложение, не требования («должен»), и
    признак процесса: «Шаг N» у пунктов, слова о порядке действий в названии раздела или во вводной фразе."""
    texts = [it["text"] for it in lst["items"]]
    if len(texts) < LIST_STEPS_MIN or sum(len(t) for t in texts) / len(texts) < 25:
        return False                             # перечень коротких названий, а не шаги
    if sum(1 for t in texts if _MODAL_RE.search(t)) * 2 >= len(texts):
        return False                             # «… должен …» — список требований
    if lst["kind"] == "step":
        return True                              # «Шаг 1. …», «Этап 2: …»
    lead = lst["lead"]
    strong = _PROCESS_STRONG_RE.search(lead) or _PROCESS_STRONG_RE.search(title)
    if _NOT_PROCESS_RE.search(lead) or (_NOT_PROCESS_RE.search(title) and not _PROCESS_STRONG_RE.search(lead)):
        return False
    if (_LIST_OF_RE.search(lead) or _LIST_OF_RE.search(title)) and not strong:
        return False
    if strong:
        return True
    # «процесс», «взаимодействие» — признак слабее: нужна вводная фраза с двоеточием или нумерованный список
    weak = _PROCESS_WEAK_RE.search(lead) or _PROCESS_WEAK_RE.search(title)
    return bool(weak and (lead.endswith(":") or lst["kind"] == "number"))


def _sections(blocks):
    """Разделы документа — блоки текста между заголовками: [(начало, конец)]."""
    out, start = [], None
    for j, b in enumerate(blocks + [{"level": 1}]):
        if b["level"]:
            if start is not None and j > start:
                out.append((start, j))
            start = j + 1
        elif start is None:
            start = j
    return out


def _section_end(blocks, j):
    """Последний блок раздела с заголовком j (вместе с подразделами)."""
    k = j
    while k + 1 < len(blocks) and not (blocks[k + 1]["level"] and blocks[k + 1]["level"] <= blocks[j]["level"]):
        k += 1
    return k


def _heading_steps(blocks):
    """Подразделы «Шаг 1 …», «Этап 2 …» одного уровня подряд (не меньше LIST_STEPS_MIN) — процесс: шаг —
    название и текст подраздела. → [{kind, path (раздел над шагами), index, steps: [(номер, текст)], inner}]."""
    out, run = [], []

    def flush():
        if len(run) >= LIST_STEPS_MIN:
            steps = []
            for j, no, name in run:
                body = [" ".join(b["text"].split()) for b in blocks[j + 1:_section_end(blocks, j) + 1] if not b["level"]]
                steps.append((no, (name + (": " + " ".join(body) if body else "")).strip()))
            first = blocks[run[0][0]]
            out.append({"kind": "headings", "path": first["path"].rsplit(" → ", 1)[0] if " → " in first["path"] else "",
                        "index": _section_end(blocks, run[-1][0]), "steps": steps,
                        "inner": [blocks[j]["path"] for j, _n, _t in run]})
        run.clear()

    for j, b in enumerate(blocks):
        if not b["level"]:
            continue
        level = blocks[run[-1][0]]["level"] if run else 0
        if run and b["level"] < level:
            flush()
        title = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", b["title"])
        m = _STEP_WORD_RE.match(title)
        if run and b["level"] > level:
            continue                             # подзаголовок внутри шага
        if m:
            run.append((j, m.group(1), title[m.end():].strip(" .") or title))
        elif run:
            flush()
    flush()
    return out


def find_processes(blocks):
    """Все описания процесса в документе: таблицы операций (find_process_tables), списки шагов и подразделы
    «Шаг N». → [{kind: "table" | "list" | "headings", path, index (последний блок описания), steps: [(номер,
    шаг одной строкой «Шаг N: …»)]; у таблицы — ещё header и rows}]."""
    out = []
    for t in find_process_tables(blocks):
        steps = [(_step_no(r, i), step_text(t["header"], r, i)) for i, r in enumerate(t["rows"])]
        out.append({**t, "kind": "table", "steps": steps})
    with_table = {p["path"] for p in out}
    headings = [h for h in _heading_steps(blocks) if h["path"] not in with_table]
    inner = [x for h in headings for x in h["inner"]]
    text_based = []
    for start, end in _sections(blocks):
        path = blocks[start]["path"]
        if path in with_table or any(path == x or path.startswith(x + " → ") for x in inner):
            continue                             # процесс раздела уже описан таблицей или разделами «Шаг N»
        title = path.split(" → ")[-1] if path else ""
        for lst in _list_items(blocks, start, end):
            if _is_process_list(lst, title):
                steps = []
                for i, it in enumerate(lst["items"]):
                    no = it["no"] if lst["kind"] != "bullet" and it["no"] else str(i + 1)
                    steps.append((no, it["text"]))
                text_based.append({"kind": "list", "path": path, "index": lst["last"], "steps": steps})
    for h in headings:
        text_based.append({k: v for k, v in h.items() if k != "inner"})
    text_based.sort(key=lambda p: p["index"])
    for p in text_based:
        p["steps"] = [(no, tr("Шаг {n}: {body}", n=no, body=text[:STEP_CHARS_MAX])) for no, text in p["steps"]]
    return out + text_based[:TEXT_PROCESSES_MAX]


def process_summary(processes):
    """Строка лога: какие описания процесса нашла глубокая проверка."""
    kinds = {"table": tr("таблица"), "list": tr("список"), "headings": tr("разделы «Шаг N»")}
    return "; ".join(tr("«{s}» — {k}, шагов: {n}", s=section_label(p["path"]) or tr("начало документа"),
                        k=kinds[p["kind"]], n=len(p["steps"])) for p in processes)


# ---------------------------------------------------------------- цифры

_DATA_UNITS = {"кб": 2 ** 10, "kb": 2 ** 10, "мб": 2 ** 20, "mb": 2 ** 20, "гб": 2 ** 30, "gb": 2 ** 30,
               "тб": 2 ** 40, "tb": 2 ** 40}
_QTY_RE = re.compile(r"(?i)(?<![\d.,])(\d{1,3}(?:[  ]\d{3})+|\d+)(?:[.,](\d+))?\s?(тб|гб|мб|кб|tb|gb|mb|kb)(?![а-яёa-z])")
_PERIODS = (("message", re.compile(r"(?i)одн\w*\s+(?:\w+\s+)?(?:документ|сообщени|файл|пакет)|в рамках одного|"
                                   r"per message|single message|one message")),
            ("day", re.compile(r"(?i)сутк|сут\.|в день|ежедневн|per day|daily|a day")),
            ("month", re.compile(r"(?i)месяц|в мес|/мес|per month|monthly")),
            ("year", re.compile(r"(?i)\bгод|в год|/год|за год|per year|annual|yearly")))
_STATS = (("avg", re.compile(r"(?i)средн|average|mean")),
          ("max", re.compile(r"(?i)максим|не более|пиков|maximum|\bmax|peak|at most")),
          ("min", re.compile(r"(?i)миним|не менее|minimum|\bmin|at least")))
_PER = {("day", "year"): 365, ("day", "month"): 30, ("month", "year"): 12}


def _classify(label, rules):
    return next((name for name, rx in rules if rx.search(label or "")), None)


def _fmt_bytes(n):
    for unit, size in (("Тб", 2 ** 40), ("Гб", 2 ** 30), ("Мб", 2 ** 20), ("Кб", 2 ** 10)):
        if n >= size:
            v = n / size
            return (f"{v:.0f}" if v >= 100 else f"{v:.1f}" if v >= 10 else f"{v:.2f}").replace(".", ",") + " " + unit
    return f"{n:.0f} б"


def extract_quantities(blocks):
    """Показатели объёма данных из документа: строки таблиц «показатель | значение» и фразы с числом и единицей.
    → [{section, label, value, bytes, period, stat}]."""
    facts = []

    def add(label, m, path):
        whole = int(re.sub(r"\D", "", m.group(1)))
        num = whole + (float("0." + m.group(2)) if m.group(2) else 0)
        facts.append({"section": section_label(path), "label": label.strip()[:160], "value": m.group(0).strip(),
                      "bytes": num * _DATA_UNITS[m.group(3).lower()], "period": _classify(label, _PERIODS),
                      "stat": _classify(label, _STATS)})

    for b in blocks:
        if b["level"]:
            continue
        if _is_table(b["text"]):
            header, rows = table_rows(b["text"])
            for r in [header] + rows:
                cells = [c for c in r if c]
                if len(cells) < 2:
                    continue
                label = cells[1] if _STEP_NO_RE.match(cells[0]) and len(cells) > 2 else cells[0]
                for c in cells[1:]:
                    if c is label:
                        continue
                    for m in _QTY_RE.finditer(c):
                        add(label, m, b["path"])
        else:
            for sentence in re.split(r"(?<=[.;!?])\s+", b["text"]):
                for m in _QTY_RE.finditer(sentence):
                    add(sentence, m, b["path"])
    return facts


def quantity_calculations(facts):
    """Расчёты, которые модели лучше не доверять: сутки × 365 против года, сутки × 30 против месяца, месяц × 12
    против года; среднее больше максимума. Только расхождения больше чем вдвое."""
    out = []
    for a in facts:
        for b in facts:
            k = _PER.get((a["period"], b["period"]))
            if not k or a is b:
                continue
            est = a["bytes"] * k
            ratio = b["bytes"] / est if est else 0
            if a["stat"] == "max":
                bad = b["bytes"] > est * 1.05            # за год больше, чем возможно при максимуме каждый день
            else:
                bad = ratio > 2 or ratio < 0.5
            if bad and ratio:
                times = ratio if ratio >= 1 else 1 / ratio
                out.append(tr("«{a}» ({av}, раздел «{sa}») × {k} = {est}; «{b}» — {bv} (раздел «{sb}»): {how} в {r} раза",
                              a=a["label"], av=a["value"], sa=a["section"], k=k, est=_fmt_bytes(est), b=b["label"],
                              bv=b["value"], sb=b["section"], r=f"{times:.1f}".replace(".", ","),
                              how=tr("больше") if ratio >= 1 else tr("меньше")))
    for a in facts:
        for b in facts:
            if (a["stat"], b["stat"]) == ("avg", "max") and a["period"] == b["period"] and a["period"] \
                    and a["bytes"] > b["bytes"]:
                out.append(tr("Среднее «{a}» ({av}) больше максимума «{b}» ({bv})", a=a["label"], av=a["value"],
                              b=b["label"], bv=b["value"]))
    return list(dict.fromkeys(out))


# ---------------------------------------------------------------- оформление (без модели)

_PSEUDO_HEAD_RE = re.compile(r"^(\d+(?:\.\d+)+)\.?\s+([А-ЯЁA-Z][^\n]{2,90}?)\.?$")
_TOC_LINE_RE = re.compile(r"^(?:(\d+(?:\.\d+)*)\.?\s+)?(\S.{2,150}?)(?:\s*(?:\.{3,}|…+|\t)\s*|\s+)(\d{1,3})$")
_HEAD_NO_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s")
_SKIP_TABLE_RE = re.compile(r"(?i)приложени|реестр|шаблон|форма|appendix|template")
# В таком разделе бывает только рисунок (схема процесса), а рисунки из Word разбор документа может не передать
_PICTURE_TITLE_RE = re.compile(r"(?i)модел|схем|диаграм|рисун|model|diagram|figure|scheme")


_APPENDIX_RE = re.compile(r"^(?:приложение|appendix)\s+[a-zа-я0-9]{1,3}\b[.:]?\s*(?:[-–—]\s*)?")
_CAPTION_RE = re.compile(r"(?i)^(?:таблица|рисунок|table|figure)\s+[\w.]+")


def _norm_title(t):
    """Название раздела для сравнения содержания с заголовками: без номера и без «Приложение А» — его часто
    добавляет нумерация Word, и в тексте заголовка его нет."""
    t = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", (t or "").lower().replace("ё", "е"))
    t = _APPENDIX_RE.sub("", t) or t
    return re.sub(r"[^0-9a-zа-я]+", " ", t).strip()[:40]


def _toc_entries(blocks):
    """Строки содержания «2.1 Название … 7» в начале документа (не меньше трёх подряд)."""
    entries, run = [], []
    lines = []
    for b in blocks[: max(10, len(blocks) // 2)]:
        if b["level"] or _is_table(b["text"]):
            lines.append(None)
            continue
        # строка содержания бывает выделена жирным целиком («**1.\tОбщие положения\t3**»)
        lines += [ln.strip().strip("*_").strip() for ln in b["text"].split("\n")]
    for ln in lines + [None]:
        m = _TOC_LINE_RE.match(ln) if ln else None
        if m and len(ln) < 170:
            if not _CAPTION_RE.match(m.group(2)):   # «Таблица А.1 – …» в содержании — подпись, а не раздел
                run.append((m.group(1) or "", m.group(2).strip()))
        else:
            if len(run) >= 3:
                entries += run
            run = []
    return entries


def _finding(severity, text, sections=()):
    return {"severity": severity, "quote": "", "part": None,
            "sections": [s for s in sections if s], "source": "check", "text": text}


def check_formatting(blocks):
    """Оформление без модели: пункт, оформленный обычным текстом вместо заголовка; расхождение содержания с
    заголовками; пустые таблицы, колонки и поля; пустые разделы."""
    out = []
    headings = [b for b in blocks if b["level"]]
    toc = _toc_entries(blocks)
    known_nums = {m.group(1) for b in headings if (m := _HEAD_NO_RE.match(b["title"] + " "))} | {n for n, _t in toc if n}

    # 1. пункт текстом вместо заголовка
    pseudo = []
    for j, b in enumerate(blocks):
        t = b["text"].strip()
        if b["level"] or "\n" in t or _is_table(t):
            continue
        m = _PSEUDO_HEAD_RE.match(t)
        if not m or re.search(r"[.;:!?]\s", m.group(2)) or re.search(r"(?:\t|\.{3,}|…|\s)\s*\d{1,3}$", t):
            continue                             # строка содержания («1.1 Назначение документа 3») — не пункт
        num = m.group(1)
        nxt = blocks[j + 1]["text"].lstrip() if j + 1 < len(blocks) else ""
        has_children = nxt.startswith(num + ".")
        # «3.4 Приёмка работ» — заголовок; «3.1. Система должна …» с точкой — пункт требований, если у
        # него нет подпунктов («2.2.4. Требования …» и следом «2.2.4.1.» — заголовок)
        if has_children or (not t.endswith(".") and num.rsplit(".", 1)[0] in known_nums):
            pseudo.append(f"{num} {m.group(2).strip().rstrip('.')}")
    if pseudo:
        out.append(_finding("НИЗКИЙ", tr("Пункты оформлены обычным текстом, а не заголовком (стилем заголовка): {v}. "
                                         "Поэтому они не попадают в структуру документа и в содержание.",
                                         v="; ".join(f"«{p}»" for p in pseudo[:8]))))

    # 2. содержание и заголовки
    if toc:
        head_titles = {_norm_title(b["title"]) for b in headings}
        toc_titles = {_norm_title(t) for _n, t in toc}
        missing = [f"{n} {t}".strip() for n, t in toc if _norm_title(t) not in head_titles
                   and not any(h.startswith(_norm_title(t)[:25]) for h in head_titles)]
        extra = [b["title"] for b in headings[1:] if b["level"] >= 2 and _norm_title(b["title"]) not in toc_titles
                 and not any(x.startswith(_norm_title(b["title"])[:25]) for x in toc_titles)
                 and not re.search(r"(?i)содержани|оглавлени|contents", b["title"])]
        if missing:
            out.append(_finding("НИЗКИЙ", tr("В содержании есть разделы, которых нет среди заголовков документа: {v}.",
                                             v="; ".join(f"«{x}»" for x in missing[:8]))))
        if extra:
            out.append(_finding("НИЗКИЙ", tr("Разделы документа, которых нет в содержании: {v}.",
                                             v="; ".join(f"«{x}»" for x in extra[:8]))))

    # 3. пустые таблицы, колонки и поля
    for b in blocks:
        if b["level"] or not _is_table(b["text"]) or _SKIP_TABLE_RE.search(b["path"] or ""):
            continue
        header, rows = table_rows(b["text"])
        where = section_label(b["path"]) or tr("начало документа")
        if not rows or not header:
            continue
        if all(not any(r) for r in rows):
            out.append(_finding("НИЗКИЙ", tr("Таблица в разделе «{s}» не заполнена.", s=where), [where]))
            continue
        if len(header) == 2 and _filled(header) == 2:
            empty = [r[0] for r in [header] + rows if r[0] and not r[1]]
            if empty and len(empty) < len(rows):
                out.append(_finding("СРЕДНИЙ", tr("В таблице раздела «{s}» не заполнено: {v}.", s=where,
                                                  v="; ".join(f"«{x}»" for x in empty[:8])), [where]))
            continue
        # строки с данными: не меньше двух заполненных ячеек (строка «Зона …» на всю ширину таблицы — не данные;
        # колонка «№» бывает пустой у всех строк)
        considered = [r for r in rows if _filled(r) >= 2]
        if len(header) >= 3 and len(considered) >= 2:
            empty_cols = [header[k] for k in range(1, len(header)) if header[k] and all(not r[k] for r in considered)]
            if empty_cols:
                out.append(_finding("СРЕДНИЙ", tr("В таблице раздела «{s}» не заполнены колонки: {v}.", s=where,
                                                  v="; ".join(f"«{x}»" for x in empty_cols)), [where]))

    # 4. пустые ячейки в таблице операций: шаг без исполнителя, сервиса, входа или результата
    for t in find_process_tables(blocks):
        gaps = []
        for i, r in enumerate(t["rows"]):
            empty = [t["header"][k] for k in range(1, len(t["header"])) if t["header"][k] and not r[k]]
            if empty:
                gaps.append(tr("шаг {n} — {v}", n=_step_no(r, i), v=", ".join(f"«{x}»" for x in empty)))
        if gaps:
            where = section_label(t["path"]) or tr("начало документа")
            out.append(_finding("СРЕДНИЙ", tr("В таблице операций раздела «{s}» не заполнено: {v}.", s=where,
                                              v="; ".join(gaps[:10])), [where]))

    # 5. пустые разделы
    empty_sections = []
    for j, b in enumerate(blocks):
        if not b["level"] or j == 0:
            continue
        nxt = blocks[j + 1] if j + 1 < len(blocks) else None
        if (nxt is None or (nxt["level"] and nxt["level"] <= b["level"])) and not _PICTURE_TITLE_RE.search(b["title"]):
            empty_sections.append(b["title"])
    if empty_sections:
        out.append(_finding("НИЗКИЙ", tr("Разделы без текста: {v}.", v="; ".join(f"«{x}»" for x in empty_sections[:8]))))
    return out


# ---------------------------------------------------------------- задачи для модели

PRIORITY = ("boundary", "step", "requirement", "numbers", "claims", "conflict", "language")
STEP_PAIRS_MAX = 20         # пар шагов на одну таблицу операций
REQUIREMENTS_MAX = 20       # требований к процессу на одну таблицу
CLAIMS_PER_TOPIC_MAX = 30   # утверждений одной темы в одном вопросе


def _task(kind, title, system_key, user, sections=(), **extra):
    return {"kind": kind, "title": title, "system_key": system_key, "user": user,
            "sections": [s for s in sections if s], **extra}


def build_deep_tasks(blocks, parts):
    """Задачи первого этапа (по документу): процесс (таблица операций, список шагов или разделы «Шаг N» —
    find_processes), цифры, утверждения частей, опечатки."""
    tasks = []
    for t in find_processes(blocks):
        label = section_label(t["path"]) or tr("начало документа")
        nos, steps = [no for no, _s in t["steps"]], [s for _no, s in t["steps"]]
        steps_text = "\n".join(steps)
        info, reqs = process_info(blocks, t)
        context = "\n".join(info + reqs) or tr("(сведений и требований к процессу в документе не найдено)")
        if info:
            tasks.append(_task("boundary", tr("Границы процесса «{s}»", s=label), "deep_boundary_system",
                               render("deep_boundary_user", context="\n".join(info), section=label, steps=steps_text),
                               [label]))
        for i in range(min(len(steps) - 1, STEP_PAIRS_MAX)):
            a, b = nos[i], nos[i + 1]
            tasks.append(_task("step", tr("Процесс «{s}»: шаг {a} → шаг {b}", s=label, a=a, b=b), "deep_step_system",
                               render("deep_step_user", context=context, section=label, steps=steps_text,
                                      pair=steps[i] + "\n" + steps[i + 1]), [label]))
        for req in reqs[:REQUIREMENTS_MAX]:
            tasks.append(_task("requirement", tr("Процесс «{s}»: требование «{r}»", s=label, r=req[:60]),
                               "deep_requirement_system",
                               render("deep_requirement_user", requirement=req, section=label, steps=steps_text,
                                      context="\n".join(info) or "—"), [label]))
    facts = extract_quantities(blocks)
    calc = quantity_calculations(facts)
    if calc or len(facts) >= 4:
        lines = [f"«{f['section']}» — {f['label']} — {f['value']}" for f in facts[:60]]
        tasks.append(_task("numbers", tr("Согласованность цифр"), "deep_numbers_system",
                           render("deep_numbers_user", facts="\n".join(lines),
                                  calc="\n".join(calc) or tr("расхождений больше чем вдвое не найдено")),
                           calc=calc))
    topics = claim_topics()
    for p in parts:
        label = section_label(p["path"]) or tr("начало документа")
        tasks.append(_task("claims", tr("Утверждения части «{s}»", s=label), "deep_claims_system",
                           render("deep_claims_user", section=label, text=p["text"]), [label],
                           topics="; ".join(topics)))
    for p in parts:
        label = section_label(p["path"]) or tr("начало документа")
        tasks.append(_task("language", tr("Опечатки: «{s}»", s=label), "deep_language_system",
                           render("deep_language_user", text=p["text"]), [label]))
    return tasks


def claim_topics():
    return [t.strip() for t in prompt_text("deep_claim_topics").split("\n") if t.strip()]


def conflict_tasks(claims):
    """Задачи второго этапа: утверждения одной темы (из разных разделов или одного) — сравнить. claims — [(тема,
    утверждение, раздел)]."""
    topics = claim_topics()
    by_topic = {}
    for topic, claim, section in claims:
        key = next((t for t in topics if t.lower() == (topic or "").strip().lower()), None)
        if key:
            by_topic.setdefault(key, []).append((section, claim))
    tasks = []
    for topic in topics:
        items = list(dict.fromkeys(by_topic.get(topic) or []))
        if len(items) < 2:          # противоречие бывает и внутри одного раздела («содержит ПД» — «ПД не обрабатываются»)
            continue
        lines = [f"«{s}»: {c}" for s, c in items[:CLAIMS_PER_TOPIC_MAX]]
        tasks.append(_task("conflict", tr("Противоречия: {t}", t=topic), "deep_conflict_system",
                           render("deep_conflict_user", topic=topic, claims="\n".join(lines))))
    return tasks


def run_task(task, cfg, attempts=1):
    """Один вопрос модели → запись: findings (теги критичности) или claims (утверждения для второго этапа)."""
    from .audit import (DEEP_FINDINGS_MAX, DEEP_KIND_MAX, cap_findings, finding_from_line, format_finding,
                        is_clean_report, is_llm_error, parse_findings)
    from .services import answer_label
    t0 = time.time()
    system = prompt_text(task["system_key"])
    if task["kind"] == "claims":
        system = render("deep_claims_system", topics=task.get("topics", ""))
    with answer_label(task["title"]):
        raw = ask_llm(system, task["user"], cfg, guard=True)
    entry = {"kind": "deep", "check": task["kind"], "title": task["title"], "failed": is_llm_error(raw),
             "report": "", "findings": [], "claims": [], "attempts": attempts, "sources": [], "dropped": [],
             "no_norms": False}
    if entry["failed"]:
        entry["report"] = raw.strip()
    elif task["kind"] == "claims":
        data = extract_json(raw, kind="array")
        section = (task["sections"] or [""])[0]
        for d in data if isinstance(data, list) else []:
            if isinstance(d, dict) and str(d.get("claim") or "").strip():
                entry["claims"].append((str(d.get("topic") or "").strip(), str(d["claim"]).strip()[:400], section))
        entry["report"] = "\n".join(f"- [{t}] {c}" for t, c, _s in entry["claims"]) or tr("Утверждений нет.")
    elif is_clean_report(raw) or len(raw.strip()) < 15:
        entry["report"] = tr("Часть чистая")
    else:
        for line in parse_findings(raw):
            f = finding_from_line(line)
            if len(f["text"]) > 15:
                entry["findings"].append({**f, "sections": list(task["sections"]), "source": "deep",
                                          "check": task["kind"]})
        found = entry["findings"]
        entry["findings"], _over = cap_findings(found, DEEP_KIND_MAX.get(task["kind"], DEEP_FINDINGS_MAX))
        entry["report"] = "\n".join(format_finding(f) for f in entry["findings"]) or tr("Часть чистая")
        over = [f for f in found if not any(f is k for k in entry["findings"])]
        if over:        # в логе видно, что отброшено сверх лимита на этот вопрос
            entry["report"] += ("\n\n" + tr("**Сверх лимита (в заключение не вошли):**") + "\n"
                                + "\n".join(format_finding(f) for f in over))
    if task["kind"] == "numbers" and entry["failed"] and task.get("calc"):
        entry["fallback"] = [_finding("НИЗКИЙ", tr("Проверьте согласованность показателей: {v}", v=c)) for c in task["calc"]]
    entry["seconds"] = time.time() - t0
    return entry


def _run_task_safe(task, cfg):
    try:
        return run_task(task, cfg)
    except Exception as e:                       # сбой одной задачи не роняет аудит
        return {"kind": "deep", "check": task["kind"], "title": task["title"], "failed": True,
                "report": f"❌ {type(e).__name__}: {str(e)[:200]}", "findings": [], "claims": [],
                "attempts": 1, "seconds": 0, "sources": [], "dropped": [], "no_norms": False}


def run_tasks(tasks, cfg, on_done=None, parallel=1):
    """Задачи модели — параллельно (parallel запросов одновременно); on_done(номер, запись) вызывается в этом же
    потоке по мере готовности. → записи в порядке задач."""
    return parallel_map(lambda t: _run_task_safe(t, cfg), tasks, parallel=parallel, on_done=on_done)


def limit_tasks(tasks, max_calls):
    """Задачи в пределах лимита вызовов: сначала процесс, затем цифры, утверждения, опечатки.
    → (выбранные в исходном порядке, сколько пропущено)."""
    if max_calls <= 0 or len(tasks) <= max_calls:
        return tasks, 0
    order = sorted(range(len(tasks)), key=lambda i: (PRIORITY.index(tasks[i]["kind"]), i))
    keep = set(order[:max_calls])
    return [t for i, t in enumerate(tasks) if i in keep], len(tasks) - max_calls
