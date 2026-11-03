"""Имитация OpenAI-совместимого шлюза: /v1/models, /v1/embeddings, /v1/rerank, /v1/chat/completions."""
import hashlib
import json
import math
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATE = {"requests": [], "last_chat": None, "models": None, "rerank_fail_from": None, "rerank_count": 0,
         "shuffle_embeddings": False,   # True — элементы data в обратном порядке (порядок задаёт только index)
         "slow_words": {},              # слово в запросе → секунд задержки ответа (таймаут на стороне MINT)
         "fail_words": {}}              # слово в запросе → сколько раз ещё ответить 503

DIMS = {"emb-model": 64, "emb-model-2": 48, "emb-raw": 64, "qwen3-embedding-4b": 64}
RAW_SCALE = {"emb-raw": 3.7}
MODELS = [
    {"id": "test-llm", "object": "model", "max_model_len": 8192},
    {"id": "big-llm", "object": "model"},
    {"id": "emb-model", "object": "model", "max_model_len": 512},
    {"id": "emb-model-2", "object": "model", "max_model_len": 512},
    {"id": "rr-model", "object": "model", "max_model_len": 1024},
]


def _tokens(text):
    return [w[:5] for w in re.findall(r"[а-яёa-z0-9]+", (text or "").lower())]


def embed(text, dim):
    v = [0.0] * dim
    for t in _tokens(text):
        h = int(hashlib.md5(t.encode()).hexdigest(), 16)
        v[h % dim] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def ntok(text):
    return math.ceil(len(text or "") / 3.3) + 2


def consult_reply(system, user, en=False):
    """Консультант (mint/consult.py): разбор запроса — JSON; ответ — разделы «📄 …», варианты, схема Mermaid, ссылка
    на первый фрагмент и один пункт без ссылки (его MINT помечает ❔). None — промпт не консультанта.
    Свои ответы — STATE["consult_plan_reply"], STATE["consult_reply"]."""
    if "Ты готовишь поиск по базе знаний" in system or "You are preparing a search of the organisation" in system:
        if STATE.get("consult_plan_reply") is not None:
            return STATE["consult_plan_reply"]
        req = user.split("--- REQUEST ---" if en else "--- ЗАПРОС ---")[-1].strip()
        kind = ("diagram" if re.search(r"схем|diagram", req, re.I) else
                "problem" if re.search(r"проблем|problem", req, re.I) else "explain")
        words = re.findall(r"\w{5,}", req)[:3]
        queries = [" ".join(words) + (" composition" if en else " состав"),
                   " ".join(words) + (" interaction" if en else " взаимодействие")]
        return "```json\n" + json.dumps({"kind": kind, "systems": [], "queries": queries}, ensure_ascii=False) + "\n```"
    if "📄 Как устроено сейчас" not in system and "📄 How it works now" not in system:
        return None
    if STATE.get("consult_reply") is not None:
        return STATE["consult_reply"]
    m = re.search(r"=== (?:ИСТОЧНИК|SOURCE): (.+?)(?: \| .*)? ===", user)
    src = m.group(1).strip() if m else ("none.docx" if en else "нет.docx")
    kind = re.search(r"\((?:тип запроса по разбору|kind of request from the analysis): (\w+)", user)
    kind = kind.group(1) if kind else "other"
    n = user.count("=== ИСТОЧНИК") + user.count("=== SOURCE")
    if en:
        parts = ["### 📄 How it works now", f"- The components are described in the document [Source: {src}]",
                 "- The gateway passes messages to the queue without a delivery confirmation to the recipient.",
                 "### Solution options", "- 💡 Split the queues by flows."]
        if kind == "diagram":
            parts += ["### Diagram", "```mermaid", "sequenceDiagram", '  participant A as Sender',
                      '  participant B as Gateway', '  A->>B: Message', "```", "### Steps",
                      f"1. The sender passes the message [Source: {src}]"]
        parts += ["### Not in the base — what to clarify", f"- Monitoring is not described. Fragments: {n}."]
    else:
        parts = ["### 📄 Как устроено сейчас", f"- Компоненты описаны в документе [Источник: {src}]",
                 "- Шлюз передаёт сообщения в очередь без подтверждения доставки получателю.",
                 "### Варианты решения", "- 💡 Разделить очереди по потокам."]
        if kind == "diagram":
            parts += ["### Схема", "```mermaid", "sequenceDiagram", '  participant A as Отправитель',
                      '  participant B as Шлюз', '  A->>B: Сообщение', "```", "### Шаги",
                      f"1. Отправитель передаёт сообщение [Источник: {src}]"]
        parts += ["### Чего нет в базе и что уточнить", f"- Нет описания мониторинга. Фрагментов: {n}."]
    return "\n".join(parts)


def chat_reply_en(system, user):
    """Ответы на английские промпты (интерфейс на английском). None — промпт не английский."""
    if "You are preparing a search of the organisation" in system or "📄 How it works now" in system:
        return consult_reply(system, user, en=True)
    if "Senior Controller" in system:
        n = len(re.findall(r"^\d+\.", user.split("DRAFT FINDINGS")[-1], flags=re.M))
        chapter = user.split("--- DOCUMENT SECTION ---")[-1].split("--- REFERENCE")[0]
        sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", chapter)
                     if "personal data" in x.lower() and "#" not in x]
        out = []
        for i in range(1, n + 1):
            out.append({"n": i, "verdict": "KEEP" if i % 2 else "DROP", "severity": "CRITICAL",
                        "category": {1: "SECURITY", 3: "SLA"}.get(i, "ARCHITECTURE"),
                        "quote": (sentences[0] if sentences else "") if i == 1 else "",
                        "text": "", "reason": "checked"})
        return "```json\n" + json.dumps(out) + "\n```"
    if "lead inspector" in system:
        part = user.split("SECTIONS OF THE NEW REVISION:")[-1]
        for sent in re.split(r"(?<=[.!?])\s+|\n+", part):
            if "encrypt" in sent.lower() and "===" not in sent:
                return json.dumps({"status": "FIXED", "quote": sent.strip(), "comment": "Added."})
        return json.dumps({"status": "NOT_FIXED", "quote": "", "comment": "Not found."})
    if any(m in system for m in ("transition between two neighbouring steps", "one business process requirement",
                                 "Compare the business process information", "obvious typos",
                                 "quantitative indicators from the document", "statements on one topic")):
        return "Section is clean"
    if "List the statements from the document section" in system or "comparing a review result" in system:
        return "[]"
    if "special attention\" point for the document" in system:
        return ("Answer: partly — there are gaps.\n"
                "- [CRITICAL] 2.2.3, step 4: how the file gets from the portal to the integration platform is not described")
    if "editor of a review report" in system:
        return STATE.get("merge_reply", "[]")
    if '"Key points" block' in system:
        return STATE.get("summary_reply", "[]")
    if "says is missing is present" in system:
        return json.dumps({"found": False, "quote": "", "reason": "no"})
    if "expert reviewer" in system:
        return ("- [CRITICAL] The encryption algorithm for data transferred between subsystems is not specified\n"
                "- [LOW] The response time requirement is worded ambiguously\n"
                "- **[MEDIUM]** Retention rules for personal data processing are not taken into account")
    if "Rewrite the LAST user question" in system:
        last = user.split("--- LAST QUESTION ---")[-1].strip()
        topic = "event logs" if "log" in user.split("--- LAST QUESTION ---")[0].lower() else "the system"
        return f"<think>find the subject</think>\n{last.rstrip('?')} — about {topic}?"
    if "write one question" in system:
        frag = user.split("---", 2)[-1]
        sent = next((x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", frag) if len(x.strip()) > 30
                     and not x.strip().startswith(("#", "|", "Table", "Таблица"))), "")
        words = re.findall(r"[A-Za-zА-Яа-яЁё]{5,}", sent)[:3]
        return json.dumps({"question": "What does it say about " + " ".join(words).lower() + "?",
                           "quote": " ".join(sent.split()[:8])}, ensure_ascii=False)
    if "alternative wording" in system:
        return "Alternative: " + user.replace("Original query:", "").strip()[:200]
    if "--- CONTEXT ---" in user:
        if "[SEARCH SIGNAL" in user:          # как велит промпт: при низкой уверенности — «информации нет»
            return "The provided documents do not contain this information. Please refine the question."
        m = re.search(r"=== SOURCE: (.+?)(?: \| .*)? ===", user)
        return (f"Answer from the context. Abbreviations: {'yes' if 'ABBREVIATIONS' in user else 'no'}. "
                f"Sources: {user.count('=== SOURCE')}." + (f" [Source: {m.group(1).strip()}]" if m else ""))
    return None


def deep_reply(system, user):
    """Глубокая проверка аудита (mint/deep_checks.py) и сверка с эталоном. None — промпт не отсюда."""
    if "переход между двумя соседними шагами" in system:
        if STATE.get("step_reply"):          # свой ответ на вопрос о переходе
            return STATE["step_reply"]
        pair = user.split("--- ПРОВЕРЯЕМЫЙ ПЕРЕХОД ---")[-1]
        if "Шаг 3:" in pair and "Шаг 4:" in pair:
            return "- [КРИТИЧНЫЙ] шаг 3 → шаг 4: не описано, как отчётная форма попадает из кабинета в платформу"
        return "Часть чистая"
    if "как одно требование к бизнес-процессу отражено" in system:
        req = user.split("--- ТРЕБОВАНИЕ ---")[-1].split("--- ШАГИ")[0]
        return "- [СРЕДНИЙ] 2.1.4: в таблице нет шага расшифрования" if "шифру" in req else "Часть чистая"
    if "Сравни сведения о бизнес-процессе" in system:
        return "- [СРЕДНИЙ] Нет шага передачи итогового отчёта потребителю из границ процесса"
    if "Выпиши из главы документа утверждения" in system:
        text = user.split("---", 2)[-1].lower()
        out = []
        if "содержит персональн" in text:
            out.append({"topic": "категория данных", "claim": "данные содержат персональные данные"})
        if "не обрабатыва" in text:
            out.append({"topic": "категория данных", "claim": "персональные данные не обрабатываются"})
        if "шифру" in text:
            out.append({"topic": "шифрование и подпись", "claim": "формы шифруются на сертификат поставщика"})
        return json.dumps(out, ensure_ascii=False)
    if "утверждения из разных разделов одного документа на одну тему" in system:
        if "содержат персональные" in user and "не обрабатываются" in user:
            return "- [КРИТИЧНЫЙ] раздел 3 ↔ раздел 4: данные содержат ПД, но обработка ПД не предполагается"
        return "Часть чистая"
    if "количественные показатели из документа" in system:
        return "- [СРЕДНИЙ] объём за сутки и за год не согласованы" if " раза" in user else "Часть чистая"
    if "явные опечатки" in system:
        return "- [НИЗКИЙ] «соотвествии» → «соответствии»" if "соотвествии" in user else "Часть чистая"
    if "сверяешь результат аудита с эталоном" in system:
        if STATE.get("reference_garble", 0) > 0:        # модель ответила не по формату
            STATE["reference_garble"] -= 1
            return "Сверка [эталон]: пункт 1 найден (замечание 3), пункт 2 — нет"
        ref = user.split("--- ЭТАЛОН ---")[-1].split("--- ЗАМЕЧАНИЯ АУДИТА ---")[0]
        found = user.split("--- ЗАМЕЧАНИЯ АУДИТА ---")[-1]
        items = re.findall(r"^(\d+)\. (.+)$", ref, flags=re.M)
        fl = re.findall(r"^(\d+)\. (.+)$", found, flags=re.M)
        out = []
        for n, text in items:
            words = {w[:6] for w in re.findall(r"[а-яё]{6,}", text.lower())}
            hit = [int(k) for k, ft in fl if words & {w[:6] for w in re.findall(r"[а-яё]{6,}", ft.lower())}]
            out.append({"n": int(n), "verdict": "НАЙДЕНО" if hit else "НЕТ", "found": hit[:1], "comment": "мок"})
        if STATE.get("reference_only"):          # модель ответила не на все пункты (ответ оборван)
            only = STATE.pop("reference_only")
            out = out[:only]
        if STATE.get("reference_style") == "pretty":     # JSON с переносами строк, вердикт с значком
            for o in out:
                o["verdict"] = ("✅ " if o["verdict"] == "НАЙДЕНО" else "❌ ") + o["verdict"].lower()
                o["comment"] = f"пункт {o['n']}: " + "замечание аудита о том же месте документа и той же сути; " * 3
            return json.dumps(out, ensure_ascii=False, indent=2)
        return json.dumps(out, ensure_ascii=False)
    return None


def chat_reply(system, user, max_tokens):
    if max_tokens == 1:
        return "ok"
    en = chat_reply_en(system, user)
    if en is not None:
        return en
    consult = consult_reply(system, user)
    if consult is not None:
        return consult
    if "Старший Контролер" in system:
        n = len(re.findall(r"^\d+\.", user.split("ЧЕРНОВИК ЗАМЕЧАНИЙ")[-1], flags=re.M))
        chapter = re.split(r"--- ГЛАВА (?:ТЗ|ДОКУМЕНТА) ---", user)[-1].split("--- НОРМАТИВНЫЙ")[0]
        sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", chapter) if "ПДн" in x and "#" not in x]
        out = []
        for i in range(1, n + 1):
            out.append({"n": i, "verdict": "ОСТАВИТЬ" if i % 2 else "УДАЛИТЬ", "severity": "КРИТИЧНЫЙ",
                        "category": {1: "ИБ", 3: "SLA"}.get(i, "АРХИТЕКТУРА"),
                        "quote": (sentences[0] if sentences else "") if i == 1 else "",
                        "text": "", "reason": "проверено"})
        return "```json\n" + json.dumps(out, ensure_ascii=False) + "\n```"
    if "ведущий инспектор" in system:
        part = re.split(r"РАЗДЕЛЫ НОВОЙ РЕДАКЦИИ (?:ТЗ|ДОКУМЕНТА):", user)[-1]
        for sent in re.split(r"(?<=[.!?])\s+|\n+", part):
            if "шифрован" in sent.lower() and "===" not in sent:
                return json.dumps({"status": "ИСПРАВЛЕНО", "quote": sent.strip(), "comment": "Добавлено."},
                                  ensure_ascii=False)
        return json.dumps({"status": "НЕ_ИСПРАВЛЕНО", "quote": "", "comment": "Не найдено."}, ensure_ascii=False)
    deep = deep_reply(system, user)
    if deep is not None:
        return deep
    if "по одному пункту чек-листа" in system:     # пункт чек-листа по типу документа
        item = user.split("--- ПУНКТ ЧЕК-ЛИСТА ---")[-1].strip().split("\n")[0].lower()
        if "роли" in item:
            return "Ответ: нет — в разделе 2 роли не описаны.\n- [СРЕДНИЙ] 2: не описано, что делает роль «Оператор» в портале"
        if "сокращени" in item:
            return "**Ответ:** да — все сокращения расшифрованы в разделе 1.2."
        if "не относ" in item:
            return "Ответ: не относится — в документе нет испытаний."
        return "Ответ: частично — сроки указаны не для всех этапов.\n- [НИЗКИЙ] 4: не указан срок этапа 3"
    if "составить карточку системы" in system or "put together a card of the system" in system:
        return card_reply(system, user)
    if "Сверяешь проверяемый документ с карточкой системы" in system:
        if "«Система А»" not in system:
            return "Требований к системе нет"
        return ("- [ЕСТЬ] приём файлов через REST API (2.2) — в карточке: REST API есть\n"
                "- [ДОРАБОТКА] передача файлов до 500 Мб (2.3) — в карточке: не больше 100 Мб, 1 Гб — в планах на 2027\n"
                "- **[ПРОТИВОРЕЧИЕ]** хранение файлов 5 лет (2.4) — в карточке: файлы хранятся 1 год\n"
                "- [КРИТИЧНЫЙ] 2.4: документ рассчитывает на хранение файлов 5 лет, а Система А хранит их 1 год")
    if "Пользователь отметил пункт" in system:     # ответ на пункт «особого внимания» по всему документу
        point = user.split("--- ПУНКТ ОСОБОГО ВНИМАНИЯ ---")[-1].strip().split("\n")[0]
        return (f"Ответ: частично — по пункту «{point[:40]}» в документе есть пробелы.\n"
                "- [КРИТИЧНЫЙ] 2.2.3, шаг 4: не описано, как файл передаётся из портала в платформу интеграции\n"
                "  - и кто его получает дальше")
    if "редактор заключения аудита" in system:      # сведение повторов
        return STATE.get("merge_reply", "[]")
    if "блок «Главное»" in system:                  # «Главное» в начале заключения
        return STATE.get("summary_reply", "[]")
    if "отсутствие чего утверждает замечание" in system:     # сверка «не описано» с другими разделами
        return STATE.get("absence_reply", json.dumps({"found": False, "quote": "", "reason": "нет"}, ensure_ascii=False))
    if "эксперт-аудитор" in system and STATE.get("section_reply"):     # свой ответ проверки раздела
        return STATE["section_reply"]
    if "эксперт-аудитор" in system:
        return ("- [КРИТИЧНЫЙ] Не указан алгоритм шифрования данных при передаче между подсистемами\n"
                "- [НИЗКИЙ] Формулировка требования к времени отклика неоднозначна\n"
                "- **[СРЕДНИЙ]** 152-ФЗ не учтён при обработке персональных данных")
    if "Перепиши ПОСЛЕДНИЙ вопрос" in system:
        last = user.split("--- ПОСЛЕДНИЙ ВОПРОС ---")[-1].strip()
        topic = "журналы событий" if "урнал" in user.split("--- ПОСЛЕДНИЙ ВОПРОС ---")[0] else "систему"
        return f"<think>понять предмет</think>\n{last.rstrip('?')} — про {topic}?"
    if "сформулируй один вопрос" in system:
        frag = user.split("---", 2)[-1]
        sent = next((x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", frag) if len(x.strip()) > 30
                     and not x.strip().startswith(("#", "|", "Таблица"))), "")
        words = re.findall(r"[А-Яа-яЁё]{5,}", sent)[:3]
        return json.dumps({"question": "Что говорится про " + " ".join(words).lower() + "?",
                           "quote": " ".join(sent.split()[:8])}, ensure_ascii=False)
    if "альтернативную формулировку" in system:
        return "Альтернатива: " + user.replace("Исходный запрос:", "").strip()[:200]
    if "ВЫДУМАЙ ССЫЛКУ" in user:     # ответ с верной ссылкой и ссылкой на файл, которого нет в контексте
        m = re.search(r"=== ИСТОЧНИК: (.+?)(?: \| .*)? ===", user)
        real = m.group(1).strip() if m else "нет.docx"
        return f"Факт из базы [Источник: {real}]. Выдуманный факт [Источник: Несуществующий.docx, 9.9 Раздел]."
    if "[СИГНАЛ ПОИСКА" in user:              # как велит промпт: при низкой уверенности — «информации нет»
        return "В предоставленных документах информация отсутствует. Уточните вопрос."
    m = re.search(r"=== ИСТОЧНИК: (.+?)(?: \| .*)? ===", user)     # ссылка на первый источник контекста
    return (f"Ответ по контексту. Справочник: {'да' if 'СПРАВОЧНИК СОКРАЩЕНИЙ' in user else 'нет'}. "
            f"Источников: {user.count('=== ИСТОЧНИК')}." + (f" [Источник: {m.group(1).strip()}]" if m else ""))


def card_reply(system, user):
    """Черновик карточки системы: ответ на раздел по первому источнику контекста (см. mint/cards.py)."""
    if "card_reply" in STATE:
        return STATE["card_reply"](system, user)
    m = re.search(r"=== (?:ИСТОЧНИК|SOURCE): (.+?)(?: \| .*)? ===", user)
    src = m.group(1).strip() if m else "нет.md"
    en = "put together a card" in system
    if "«Названия»" in system or '"Names"' in system:
        return f"- СА [Источник: {src}]\n- System A [Источник: {src}]"
    if "«Что в планах" in system or '"What is planned' in system:
        return "NOT IN THE BASE" if en else "НЕТ В БАЗЕ"
    if "«Лимиты и объёмы»" in system or '"Limits and volumes"' in system:
        return (f"- размер файла — не больше 100 Мб [Источник: {src}]\n"
                "- обработка по расписанию [Источник: Выдуманный_документ.md]")
    section = re.search(r"«([^»]+)»\. Ответь|\"([^\"]+)\"\. Answer", system)
    name = (section.group(1) or section.group(2)) if section else "раздел"
    return f"- {name}: сведения из базы [{'Source' if en else 'Источник'}: {src}]"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj, headers=None):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(code)
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass                            # клиент не дождался (проверка таймаута) — это ожидаемо

    def _send_stream(self, content, finish="stop", reasoning="", delay=0.0, chunk=40):
        """Ответ потоком (Server-Sent Events, как у OpenAI): кусками по chunk символов."""
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            if reasoning:
                self._event({"choices": [{"delta": {"reasoning_content": reasoning}, "finish_reason": None}]})
            for i in range(0, len(content), chunk):
                self._event({"choices": [{"delta": {"content": content[i:i + chunk]}, "finish_reason": None}]})
                if delay:
                    time.sleep(delay)
            self._event({"choices": [{"delta": {}, "finish_reason": finish}]})
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            STATE["stream_done"] = STATE.get("stream_done", 0) + 1
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            STATE["stream_aborted"] = STATE.get("stream_aborted", 0) + 1     # клиент оборвал ответ

    def _event(self, obj):
        self.wfile.write(b"data: " + json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n\n")
        self.wfile.flush()

    def do_GET(self):
        STATE["requests"].append(("GET", self.path, None))
        if self.path.endswith("/models"):
            return self._send(200, {"object": "list", "data": STATE["models"] or MODELS})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        STATE["requests"].append(("POST", self.path, payload))
        if self.path.endswith("/embeddings"):
            dim = DIMS.get(payload.get("model"), 64)
            inp = payload.get("input")
            texts = inp if isinstance(inp, list) else [inp]
            k = RAW_SCALE.get(payload.get("model"), 1.0)
            data = [{"object": "embedding", "index": i, "embedding": [x * k for x in embed(t, dim)]}
                    for i, t in enumerate(texts)]
            if STATE["shuffle_embeddings"]:
                data.reverse()
            return self._send(200, {"data": data, "usage": {"prompt_tokens": sum(ntok(t) for t in texts)}})
        if self.path.endswith("/rerank"):
            STATE["rerank_count"] += 1
            if STATE["rerank_fail_from"] is not None and STATE["rerank_count"] >= STATE["rerank_fail_from"]:
                return self._send(500, {"error": "boom"})
            q = set(_tokens(payload.get("query")))
            res = []
            for i, d in enumerate(payload.get("documents") or []):
                dt = set(_tokens(d))
                score = len(q & dt) / (len(q) or 1)
                res.append({"index": i, "relevance_score": round(score, 4)})
            res.sort(key=lambda r: -r["relevance_score"])
            return self._send(200, {"results": res})
        if self.path.endswith("/chat/completions"):
            msgs = payload.get("messages") or []
            system = next((m["content"] for m in msgs if m["role"] == "system"), "")
            user = next((m["content"] for m in reversed(msgs) if m["role"] == "user"), "")
            STATE["last_chat"] = payload
            model = payload.get("model")
            # медленный или сбойный — проверяемый раздел (документ целиком для справки в счёт не идёт)
            target = re.split(r"--- (?:ПРОВЕРЯЕМАЯ ГЛАВА ДОКУМЕНТА|DOCUMENT SECTION UNDER REVIEW) ---", user)[-1]
            limit = STATE.get("rate_limit")        # шлюз с лимитом: столько ответов 429, затем как обычно
            if limit and limit.get("left", 0) > 0:
                limit["left"] -= 1
                limit["hits"] = limit.get("hits", 0) + 1
                return self._send(429, {"error": "rate limit"},
                                  {"Retry-After": limit["retry_after"]} if limit.get("retry_after") else None)
            for word, left in STATE["fail_words"].items():
                if left > 0 and word in target:
                    STATE["fail_words"][word] = left - 1
                    return self._send(503, {"error": "gateway overloaded"})
            for word, seconds in STATE["slow_words"].items():
                if word in target:
                    time.sleep(seconds)
            tmpl = payload.get("chat_template_kwargs") or {}
            stream = bool(payload.get("stream")) and model != "nostream-model"   # nostream-model поток не знает
            if model == "stream-strict" and payload.get("stream"):
                return self._send(400, {"error": {"message": "stream is not supported by this gateway"}})
            if model == "loop-model":         # модель зацикливается и не соблюдает max_tokens
                cycle = [f"- [НИЗКИЙ] 5.2: В документе не указано, каким образом проверяются требования к разделу 4.{i}"
                         for i in range(1, 6)]
                content = "\n".join(cycle * 300)
                if stream:
                    return self._send_stream(content, delay=0.002, chunk=120)
                return self._send(200, {"choices": [{"message": {"role": "assistant", "content": content},
                                                     "finish_reason": "stop"}]})
            if model == "long-model":         # длинный ответ без повторов, лимит max_tokens не соблюдается
                content = "\n".join(f"- [СРЕДНИЙ] {i}.1: замечание номер {i} о разных требованиях документа, все разные"
                                    for i in range(1, 400))
                if stream:
                    return self._send_stream(content, delay=0.001, chunk=200)
                return self._send(200, {"choices": [{"message": {"role": "assistant", "content": content},
                                                     "finish_reason": "stop"}]})
            if model == "strict-gw" and "chat_template_kwargs" in payload:
                return self._send(400, {"error": {"message": "Unrecognized request argument supplied: "
                                                            "chat_template_kwargs"}})
            if model == "think-model" and tmpl.get("enable_thinking") is not False:
                time.sleep(STATE.get("think_seconds", 0))    # «рассуждает», пока рассуждения не выключены
                content = chat_reply(system, user, payload.get("max_tokens"))
                if stream:
                    return self._send_stream(content, reasoning="Сначала подумаю...")
                return self._send(200, {"choices": [{"message": {"role": "assistant", "content": content,
                                                                 "reasoning_content": "Сначала подумаю..."},
                                                     "finish_reason": "stop"}],
                                        "usage": {"prompt_tokens": 10, "completion_tokens": 50,
                                                  "completion_tokens_details": {"reasoning_tokens": 40}}})
            content = chat_reply(system, user, payload.get("max_tokens"))
            finish = "stop"
            if model == "r1-model":
                if (payload.get("max_tokens") or 0) <= 20:
                    content, finish = "<think>\nДолго рассуждаю и не успеваю", "length"
                else:
                    content = "<think>\n- рассуждение: может быть, это есть в разделе 7\n- ещё мысль [1]\n</think>\n" + content
            elif model == "r1-noopen":
                content = "рассуждения без открывающего тега\n- мысль\n</think>\n" + content
            elif model == "trunc-model":
                finish = "length"
            usage = {"prompt_tokens": math.ceil((len(system) + len(user)) / 3.0) + 7, "completion_tokens": 5}
            if stream:
                return self._send_stream(content, finish=finish)
            return self._send(200, {"choices": [{"message": {"role": "assistant", "content": content},
                                                 "finish_reason": finish}], "usage": usage})
        self._send(404, {"error": "not found"})


def start():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
