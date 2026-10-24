"""Английские надписи схем: ключ — русская надпись из скриптов (пробелы и переносы сжаты до одного пробела),
значение — перевод. Сборка с --lang en без перевода хотя бы одной надписи завершается с ошибкой (lang.py)."""

EN = {
    # ---------------------------------------------------------------- build_architecture.py
    "MINT — архитектура решения":
        "MINT — solution architecture",
    "Интеллектуальная RAG-система: чат по базе знаний, аудит документов и контроль исправления замечаний. Python + Streamlit, пакет mint/; русский и английский":
        "An intelligent RAG system: knowledge base chat, document review, verification of fixes. Python + Streamlit, mint/ package; English and Russian",
    "Документы для базы (.docx, .pdf, .md, .txt): регламенты, стандарты":
        "Documents for the base (.docx, .pdf, .md, .txt): regulations, standards",
    "Вопрос пользователя":
        "User question",
    "Документ на согласование (.docx, .pdf, .md, .txt), критерии и «особое внимание»":
        "Document submitted for approval (.docx, .pdf, .md, .txt), criteria and “special attention”",
    "Выданные замечания и новая редакция документа (.docx, .pdf, .md, .txt)":
        "Issued comments and the new revision of the document (.docx, .pdf, .md, .txt)",
    "Интерфейс — Streamlit":
        "Interface — Streamlit",
    "Боковая панель: документы базы, настройки, модели и лимиты, сокращения, правила экспертов и карточки систем (черновик карточки — по базе), проверка качества, промпты, язык RU / EN, отзывы":
        "Sidebar: base documents, settings, models and limits, abbreviations, expert rules and system cards (a card draft — from the base), quality check, prompts, language EN / RU, feedback",
    "Вкладка «Чат»":
        "“Chat” tab",
    "Вкладка «Контроль исправлений»":
        "“Verification of fixes” tab",
    "ДОБАВЛЕНИЕ ДОКУМЕНТОВ В БАЗУ 1. Разбор: .docx — Docling; .pdf — без моделей (заголовки из закладок, оглавления, по шрифту); .md, .txt → текст, заголовки, таблицы 2. Нарезка по границам абзацев и предложений: parent 2500 симв. для LLM, child 400 симв. для поиска; таблицы — по строкам 3. Эмбеддинги child (вместе с путём заголовков) 4. Запись в хранилище: векторы, фрагменты, индекс слов 5. Автосбор сокращений из документов; в манифест — модель и параметры нарезки 6. Черновик карточки системы (по кнопке на боковой панели): по каждому разделу карточки — поиск по базе и ответ LLM только по найденному, у каждого факта — источник, чего нет — «нет в базе»; эксперт проверяет, дописывает и загружает карточку в базу":
        "ADDING DOCUMENTS TO THE BASE\n\n1. Parsing: .docx — Docling; .pdf — without models (headings from bookmarks, the contents page, font size); .md, .txt → text, headings, tables\n2. Chunking at paragraph and sentence boundaries: parent 2500 chars for the LLM, child 400 chars for search; tables — by rows\n3. Child embeddings (together with the heading path)\n4. Write to the store: vectors, fragments, word index\n5. Abbreviations collected from documents; the manifest records the model and the chunking parameters\n6. A system card draft (a button on the sidebar): for each card section — a search of the base and an LLM answer only from what was found, every fact with its source, gaps — “not in the base”; the expert checks it, fills it in and loads the card into the base",
    "ЧАТ ПО БАЗЕ ЗНАНИЙ 1. Уточняющий вопрос переписывается в самостоятельный по истории диалога 2. Поиск по базе → 4–5 лучших фрагментов 3. Контекст: фрагменты с файлом и разделами (соседние — одним блоком, длинные — вокруг найденного места) + справочник сокращений 4. LLM отвечает только по контексту 5. Ответ со ссылками [файл, раздел] и списком источников; ссылки сверяются с найденными фрагментами, неверные помечены ⚠; отзыв: оценка и комментарий":
        "CHAT OVER THE KNOWLEDGE BASE\n\n1. A follow-up question is rewritten into a self-contained one using the conversation history\n2. Search the base → the 4–5 best fragments\n3. Context: fragments with file and sections (neighbours as one block, long ones around the match) + abbreviation reference\n4. The LLM answers from the context only\n5. Answer with [file, section] references and a source list; references are checked against the retrieved fragments, wrong ones are marked ⚠; feedback: rating and comment",
    "КОНТРОЛЬ ИСПРАВЛЕНИЙ 1. Новая редакция документа → разделы 2. Для каждого замечания — подходящие разделы (вектор + слова + реранкер) и, по желанию, нормы из базы 3. LLM: статус «исправлено / частично / нет» и дословная цитата 4. Цитата сверяется с текстом редакции 5. Матрица контроля .md / .docx; отзыв: оценка и комментарий":
        "VERIFICATION OF FIXES\n\n1. New revision of the document → sections\n2. For each comment — matching sections (vector + words + reranker) and, optionally, norms from the base\n3. LLM: status “fixed / partially / not fixed” and a verbatim quote\n4. The quote is checked against the revision text\n5. Verification matrix .md / .docx; feedback: rating and comment",
    "Поисковый движок (общий для чата, аудита и контроля исправлений) вектор (FAISS, смысл) + слова (BM25: основы русских и английских слов, расшифровки сокращений) → слияние рангов (RRF) → реранкер (необязательно) → лучшие фрагменты + сигнал «уверенность низкая». Подробно — на схеме ниже.":
        "Search engine (shared by chat, review and verification of fixes)\nvector (FAISS, meaning) + words (BM25: stems of Russian and English words, abbreviation expansions) → rank fusion (RRF) → reranker (optional) → best fragments + the “low confidence” signal. Details — in the diagram below.",
    "Ядро MINT — Python":
        "MINT core — Python",
    "FAISS — векторы child (по ним ищет «вектор»)":
        "FAISS — child vectors (searched by “vector”)",
    "parent_store.json — фрагменты parent (их читает LLM)":
        "parent_store.json — parent fragments (read by the LLM)",
    "bm25_index.pkl — индекс слов по основам":
        "bm25_index.pkl — word index by stems",
    "auto_glossary.json — сокращения из документов":
        "auto_glossary.json — abbreviations from documents",
    "manifest.json — модель эмбеддингов и нарезка каждого документа; audit_roles.json — правила экспертов и карточки систем для аудита":
        "manifest.json — embedding model and chunking of each document; audit_roles.json — expert rules and system cards for the review",
    "sources/ — оригиналы документов для переиндексации":
        "sources/ — original documents for re-indexing",
    "Хранилище базы знаний — папка KB_DIR на машине":
        "Knowledge base store — the KB_DIR folder on the machine",
    "Внешние сервисы":
        "External services",
    "любой OpenAI-совместимый API":
        "any OpenAI-compatible API",
    "LLM — ответы, замечания, самокритика, «Главное», черновики карточек":
        "LLM — answers, findings, critique, “Key points”, card drafts",
    "Модель эмбеддингов — векторы":
        "Embedding model — vectors",
    "Реранкер — оценка релевантности (необязательно)":
        "Reranker — relevance (optional)",
    "запись":
        "write",
    "чтение":
        "read",
    "Настройки • .env — адреса API, ключи, модели, папки, язык (MINT_LANG) • config.yaml — параметры поиска и аудита (необязательно) • glossary.json — свои расшифровки сокращений (необязательно) • checklists.yaml — свои чек-листы аудита по типам документов (образец — checklists.example.yaml; файл вне папки программы — путь в MINT_CHECKLISTS) • mint/prompts/ru.yaml, en.yaml — тексты промптов по умолчанию; свои правки — prompts.yaml (страница «Промпты»); версия набора пишется в отзывы, лог аудита и проверку качества • боковая панель — изменения на время сеанса • LOG_DIR — журнал работы, отзывы пользователей (feedback.jsonl), проверки качества (eval/), сохранённые аудиты с разбором экспертов (audits/)":
        "Settings\n• .env — API addresses, keys, models, folders, language (MINT_LANG)\n• config.yaml — search and review parameters (optional)\n• glossary.json — your own abbreviation expansions (optional)\n• checklists.yaml — your own review checklists by document type (example — checklists.example.yaml; a file outside the program folder — its path in MINT_CHECKLISTS)\n• mint/prompts/ru.yaml, en.yaml — default prompt texts; your own edits — prompts.yaml (the “Prompts” page); the version of the set goes into feedback, the review log and the quality check\n• sidebar — changes for the current session\n• LOG_DIR — work log, user feedback (feedback.jsonl), quality checks (eval/), saved reviews with expert assessments (audits/)",
    "Размеры по умолчанию (MINT подстраивает их под лимиты моделей) • parent 2500 симв. ≈ 1–1,5 страницы — уходит в контекст LLM • child 400 симв. ≈ 2–3 предложения — единица векторного поиска • раздел документа в аудите 4500 симв. ≈ 3–4 страницы • фрагмент для реранкера 800 симв.":
        "Default sizes (MINT adapts them to the model limits)\n• parent 2500 chars ≈ 1–1.5 pages — goes into the LLM context\n• child 400 chars ≈ 2–3 sentences — the unit of vector search\n• document section in review 4500 chars ≈ 3–4 pages\n• fragment for the reranker 800 chars",
    "Проверка и оценка качества • check_install.py — самопроверка установки: пакеты, разбор .docx и .pdf, подключения к моделям, страница • «Проверка качества» на боковой панели (в консоли — eval_search.py) — вопросы по базе через поиск в нескольких вариантах (вектор, слова, гибрид, гибрид + реранкер): hit@k, MRR, случайна ли разница, порог «уверенность низкая», рекомендации; по желанию — ответы чата: ошибка поиска или модели, сравнение по версии промптов • разборы замечаний экспертами (файлы разбора) — tools/review_stats.py: доля верных замечаний по видам проверок, причины ошибок, что MINT пропустил • tests/ — автотесты без сети и моделей, GitHub Actions":
        "Checks and quality evaluation\n• check_install.py — installation self-check: packages, .docx and .pdf parsing, model connections, the page\n• “Quality check” in the sidebar (from the console — eval_search.py) — questions from the base run through search in several variants (vector, words, hybrid, hybrid + reranker): hit@k, MRR, whether a difference is chance, the “low confidence” threshold, recommendations; optionally chat answers: a search or a model error, compared by prompt version\n• expert assessments of findings (assessment files) — tools/review_stats.py: the share of correct findings by check kind, reasons for errors, what MINT missed\n• tests/ — automated tests without network or models, GitHub Actions",
    "Поиск по базе — как находится нужный фрагмент":
        "Searching the base — how the right fragment is found",
    "Шаги 1–5 общие для чата, аудита и контроля исправлений; шаги 6–7 — ответ в чате.":
        "Steps 1–5 are shared by chat, review and verification of fixes; steps 6–7 — the chat answer.",
    "2а. Вектор (смысл) эмбеддинг вопроса (с инструкцией, если её требует модель) → FAISS → 50 ближайших child → их parent":
        "2a. Vector (meaning)\n\nquestion embedding (with an instruction if the model needs one) → FAISS → 50 nearest children → their parents",
    "2б. Слова (BM25) основы слов (русских и английских) + расшифровки сокращений → 20 лучших parent":
        "2b. Words (BM25)\n\nword stems (Russian and English) + abbreviation expansions → 20 best parents",
    "1. Вопрос в чате уточнение переписывается по истории диалога":
        "1. Question\n\nin chat a follow-up is rewritten using the conversation history",
    "3. Слияние рангов (RRF) 16 кандидатов; найденные обоими каналами — выше":
        "3. Rank fusion (RRF)\n\n16 candidates; those found by both channels rank higher",
    "4. Реранкер необязательно: оценивает все 16 по самому релевантному фрагменту (≤ 800 симв.); его голос добавляется к слиянию":
        "4. Reranker\n\noptional: scores all 16 by their most relevant fragment (≤ 800 chars); its vote is added to the fusion",
    "5. Отбор 4–5 фрагментов без повторов, не больше 2 частей одной таблицы; сигнал «уверенность низкая» — по баллу реранкера, без него — по словам вопроса":
        "5. Select 4–5 fragments\n\nno duplicates, at most 2 parts of one table; the “low confidence” signal — by the reranker score, without one — by the question words",
    "6. Контекст для LLM фрагменты parent с файлом и разделами: соседние — одним блоком, длинные — вокруг найденного места; + справочник сокращений":
        "6. Context for the LLM\n\nparent fragments with file and sections: neighbours as one block, long ones around the match; + abbreviation reference",
    "7. Ответ только по контексту, со ссылками [файл, раздел]; ссылки сверяются с контекстом; нет ответа в базе — так и говорит":
        "7. Answer\n\nfrom the context only, with [file, section] references; references are checked against the context; no answer in the base — it says so",
    "Если сервис эмбеддингов недоступен, работает только канал «Слова». Реранкер с пунктирной рамкой — необязательный: без него поиск идёт по шагам 1–3 и 5.":
        "If the embedding service is unavailable, only the “Words” channel works. The reranker with a dashed frame is optional: without it search runs through steps 1–3 and 5.",
    "АУДИТ ДОКУМЕНТА (MAP → REDUCE) 1. Разбор документа → .md → части по разделам до 4500 симв. (раздел с таблицей — целиком); для сравнения — весь документ одним запросом 2. MAP: каждая часть — с нормами из базы, документами-основаниями (по ссылкам документа на них), правилами экспертов, карточками упомянутых систем и документом целиком для справки (не помещается в окно — с оглавлением) → LLM пишет замечания; описанный процесс — по шагам; по желанию — с рассуждениями модели 3. Самокритика (можно выключить): оставить или удалить, критичность, дословная цитата; замечание о пункте другой части отсеивается 4. Глубокая проверка: узкие вопросы — каждая пара шагов процесса, каждое требование, границы; противоречия между разделами; цифры (считает программа); опечатки 5. Проходы 2–3 (по желанию): разделы и вопросы о процессе и цифрах — ещё раз с температурой ≥ 0,4; найденное несколькими проходами — выше 6. «Особое внимание» и чек-лист по типу документа — ответ на каждый пункт по всему документу вместе с замечаниями, уже найденными другими проверками; что документ требует от каждой упомянутой системы 7. Без модели: сокращения, оформление; ссылки и цифры из замечаний сверяются с документом и нормами 8. REDUCE: повторы — по словам (в кусках одной длинной таблицы — мягче) и моделью (замечания о разных шагах процесса не сливаются); замечания — по разделам документа, в его порядке; «Главное» — модель-редактор выбирает самые важные 9. Заключение .md, документ с примечаниями Word, лог проверки и сырые ответы модели .md; сверка с эталоном; отзыв: оценка и комментарий 10. Аудит сохраняется (LOG_DIR/audits) и открывается позже; эксперт размечает замечания («беру» / «мелочь» / «неверно» с причиной) и дописывает свои → «Мои замечания» Word / .md и файл разбора для улучшения MINT":
        "DOCUMENT REVIEW (MAP → REDUCE)\n\n1. Parsing the document → .md → parts by section up to 4500 chars (a section with its table — whole); for comparison — the whole document in one request\n2. MAP: each part — with norms from the base, basis documents (by the document's references to them), expert rules, the cards of mentioned systems and the whole document for reference (if it does not fit into the window — with the outline) → the LLM writes findings; a described process — step by step; optionally — with model reasoning\n3. Self-critique (can be turned off): keep or drop, severity, verbatim quote; a finding about a clause of another part is dropped\n4. Deep review: narrow questions — each pair of process steps, each requirement, the boundaries; contradictions between sections; figures (the program calculates); typos\n5. Passes 2–3 (optional): the sections and the process and figures questions once more at temperature ≥ 0.4; what several passes found ranks higher\n6. “Special attention” and the checklist for the document type — an answer per item from the whole document, together with the findings other checks already made; what the document requires from each mentioned system\n7. Without the model: abbreviations, formatting; references and figures in findings are checked against the document and the norms\n8. REDUCE: duplicates — by words (more leniently in the pieces of one long table) and by the model (findings about different process steps are not merged); findings by document section, in document order; “Key points” — an editor model picks the most important\n9. Report .md, the document with Word comments, the review log and raw model answers .md; comparison with a reference; feedback: rating and comment\n10. The review is saved (LOG_DIR/audits) and can be opened later; the expert marks the findings (“keep” / “minor” / “wrong” with a reason) and adds their own → “My findings” as Word / .md and an assessment file for improving MINT",
    "Вкладка «Аудит документа»: документ, критерии, «особое внимание», ⚙️ настройки аудита в одном блоке, «Мои аудиты»":
        "“Document review” tab: the document, criteria, “special attention”, ⚙️ review settings in one block, “Saved reviews”",
    "черновик карточки":
        "card draft",
    # ---------------------------------------------------------------- build_engineering.py
    "MINT — инженерная схема: устройство и настройка параметров":
        "MINT — engineering diagram: how it works and how to tune parameters",
    "По коду MINT 20.1 и новее (пакет mint/) и eval_search.py. Для администратора: что задать при установке, что MINT рассчитает сам, что подобрать тестами на своих данных и от каких особенностей компании это зависит. Каждый факт указан в одном месте; «панель N» — где искать подробности.":
        "Based on the code of MINT 20.1 and later (the mint/ package) and eval_search.py. For the administrator: what to set at installation, what MINT computes itself, what to tune with tests on your own data, and which features of your organisation it depends on. Every fact appears in one place; “panel N” tells where to find details.",
    "[Р] ВРУЧНУЮ — задаёт администратор: .env, config.yaml, панель":
        "[M] MANUAL — set by the administrator: .env, config.yaml, sidebar",
    "[А] АВТО — MINT рассчитывает по моделям и базе; трогать, если есть предупреждение или так требуют тесты":
        "[A] AUTO — MINT computes it from the models and the base; touch it only if there is a warning or tests call for it",
    "[Т] ТЕСТ — подбирается проверкой качества на своём наборе вопросов":
        "[T] TEST — tuned with the quality check on your own question set",
    "[П] ПРОВЕРКА — подбирается вручную на живых примерах":
        "[C] CHECK — tuned by hand on live examples",
    "[У] УМОЛЧАНИЕ — обычно не трогать":
        "[D] DEFAULT — usually leave as is",
    "♻ — действует на документы, загруженные после изменения; уже загруженные — переиндексация":
        "♻ — applies to documents uploaded after the change; documents already uploaded need re-indexing",
    "◆ ОПОРНЫЙ ПАРАМЕТР — от него MINT рассчитывает другие: лимиты моделей, chars_per_token, max_tokens, top_k и промежуточные chat_budget / llm_budget. Меняете его — меняются зависимые.":
        "◆ KEY PARAMETER — MINT derives others from it: model limits, chars_per_token, max_tokens, top_k and the intermediate chat_budget / llm_budget. Change it — the dependent ones change.",
    "◇ ВЛИЯЕТ НА СОСЕДНИЙ — от него зависят 1–2 параметра той же группы (parent_size → parent_overlap, audit_map_size → audit_context_max_chars …). Зависимые перечислены в колонке «Ограничения и зависимости».":
        "◇ AFFECTS A NEIGHBOUR — 1–2 parameters of the same group depend on it (parent_size → parent_overlap, audit_map_size → audit_context_max_chars …). Dependants are listed in the “Constraints and dependencies” column.",
    "ТОКЕНЫ И СИМВОЛЫ — две единицы длины текста на этой схеме • [ток.] токены — так длину считают модели: токен — кусок слова (часто 2–4 буквы). В токенах заданы лимиты моделей (llm_context_tokens, embed_max_tokens, rerank_max_tokens) и длина ответа max_tokens. • [симв.] символы — так текст режет MINT (фрагменты, разделы документа, контекст). Все размеры фрагментов и объёмы контекста — в символах. • Перевод: chars(t) = t × chars_per_token × 0.85, где 0.85 (LIMIT_SAFETY) — запас 15 % на неточность оценки. Пример: 1000 ток. × 2.5 × 0.85 = 2125 симв., которые MINT позволит себе отправить.":
        "TOKENS AND CHARACTERS — two units of text length on this diagram\n• [tok.] tokens — how models count length: a token is a piece of a word (often 2–4 letters). Model limits (llm_context_tokens, embed_max_tokens, rerank_max_tokens) and the answer length max_tokens are in tokens.\n• [chars] characters — how MINT cuts text (fragments, document sections, context). All fragment sizes and context budgets are in characters.\n• Conversion: chars(t) = t × chars_per_token × 0.85, where 0.85 (LIMIT_SAFETY) is a 15 % margin for estimation error. Example: 1000 tok. × 2.5 × 0.85 = 2125 chars that MINT will allow itself to send.",
    "СКОЛЬКО СИМВОЛОВ В ТОКЕНЕ (chars_per_token) • русский текст: 2.3–3 на современных многоязычных токенизаторах (Qwen2.5 / Qwen3, Llama 3); 1.5–2 на старых, «английских» (Llama 2, ранние Mistral) • английский текст: ≈ 4 (3.5–4.5); таблицы, номера, коды: 1.5–2.5 • 2.5 — НЕ вычисляется само: это типовое значение (FALLBACK_LIMITS), пока ничего не измерено. Вычисляется только по кнопке «Определить у сервера»: measure_chars_per_token() отправляет LLM образец на языке базы (kb_language(): русская — русский, английская — английский, смешанная или пустая — оба, берётся меньшее) и он же × 4, cpt = разница символов / разница prompt_tokens (служебные токены сокращаются). Результат живёт до перезапуска MINT — закрепить: config.yaml → models: chars_per_token. • одно значение берётся и для эмбеддингов, и для реранкера, хотя токенизаторы у них свои — ещё одна причина для запаса 15 %.":
        "HOW MANY CHARACTERS PER TOKEN (chars_per_token)\n• Russian text: 2.3–3 on modern multilingual tokenizers (Qwen2.5 / Qwen3, Llama 3); 1.5–2 on older “English” ones (Llama 2, early Mistral)\n• English text: ≈ 4 (3.5–4.5);  tables, numbers, codes: 1.5–2.5\n• 2.5 is NOT computed by itself: it is the typical value (FALLBACK_LIMITS) until something is measured. It is measured only by the “Detect from server” button: measure_chars_per_token() sends the LLM a sample in the language of the base (kb_language(): Russian base — Russian, English — English, mixed or empty — both, the lower value is used) and the same sample × 4; cpt = difference in characters / difference in prompt_tokens (service tokens cancel out). The result lives until MINT restarts — to pin it: config.yaml → models: chars_per_token.\n• one value is used for embeddings and the reranker too, although their tokenizers differ — one more reason for the 15 % margin.",
    "1. Как MINT устанавливает параметры при запуске":
        "1. How MINT sets parameters at startup",
    "Каждый перезапуск страницы: main() → _base_settings() → resolve_model_limits() → resolve_settings(). Слева — откуда берутся значения, в центре — функции, которые их соединяют, справа — что чего важнее.":
        "On every page rerun: main() → _base_settings() → resolve_model_limits() → resolve_settings(). Left — where values come from, centre — the functions that combine them, right — what takes precedence.",
    "Откуда берутся значения":
        "Where values come from",
    "[Р] .env → load_settings() → _load_env_files() куда подключаться: адреса и ключи API, имена моделей, папки, сертификат. Полный список — панель 3, «Подключения».":
        "[M] .env → load_settings() → _load_env_files()\nwhere to connect: API addresses and keys, model names, folders, certificate. Full list — panel 3, “Connections”.",
    "[Р] config.yaml → load_settings() как работать: лимиты моделей, поиск, аудит. Указанные параметры запоминаются (explicit_fields); подключения здесь игнорируются, неизвестные параметры — предупреждение в панели.":
        "[M] config.yaml → load_settings()\nhow to work: model limits, search, review. Parameters set here are remembered (explicit_fields); connections here are ignored, unknown parameters give a warning in the sidebar.",
    "[А] Серверы моделей → detect_server_info() GET …/models → context_from_model_info(): окно LLM (max_model_len, context_length, n_ctx …), вход эмбеддингов и реранкера — если сервер сообщает; кэш 10 мин.":
        "[A] Model servers → detect_server_info()\nGET …/models → context_from_model_info(): LLM window (max_model_len, context_length, n_ctx …), embedding and reranker input — if the server reports them; cached for 10 min.",
    "[А] Кнопка «Определить у сервера» → measure_chars_per_token() измеряет «символов на токен» на языке базы (как — блок «Токены и символы» вверху).":
        "[A] “Detect from server” button → measure_chars_per_token()\nmeasures “characters per token” in the language of the base (how — the “Tokens and characters” block at the top).",
    "[Р] Боковая панель → st.session_state «Модели и лимиты», «Экспертные настройки»: изменения на время сеанса; «Сбросить изменения сеанса» возвращает как было.":
        "[M] Sidebar → st.session_state\n“Models and limits”, “Expert settings”: changes for the session; “Reset session changes” restores everything.",
    "[А] База знаний → kb_default_top_k() если top_k не задан (0), предлагает его по числу фрагментов в базе — 4 или 5 (подробно — панель 3, top_k).":
        "[A] Knowledge base → kb_default_top_k()\nif top_k is not set (0), suggests it from the number of fragments in the base — 4 or 5 (details — panel 3, top_k).",
    "resolve_model_limits() ← лимиты из источников слева для каждого из 4 лимитов моделей выбирает источник по приоритету (справа); ничего нет — типовое значение (почему такие — панель 3).":
        "resolve_model_limits() ← limits from the sources on the left\nfor each of the 4 model limits picks the source by precedence (right); nothing found — the typical value (why these — panel 3).",
    "embed_prefix_preset(EMBED_MODEL) подбирает префиксы запроса и документа по имени модели эмбеддингов (таблица — панель 3, embed_query_prefix).":
        "embed_prefix_preset(EMBED_MODEL)\npicks the query and document prefixes by the embedding model name (table — panel 3, embed_query_prefix).",
    "resolve_settings() → _derive() ← параметры из источников слева рассчитывает 12 параметров по лимитам моделей. Правило: значение = меньшее из умолчания и потолка модели. Большое окно не раздувает фрагменты (длинный контекст добавляет шум), маленькое уменьшает их, чтобы ничего не обрезалось. Формулы — колонка «Ограничения» в панели 3, наглядно — панель 2. Итог: cfg (неизменяемый Settings) и info {value, auto, ceiling, source} → блок «MINT рассчитал».":
        "resolve_settings() → _derive() ← parameters from the sources on the left\ncomputes 12 parameters from the model limits. Rule: value = the smaller of the default and the model's ceiling. A large window does not inflate fragments (long context adds noise), a small one shrinks them so nothing is cut off. Formulas — the “Constraints” column in panel 3, visually — panel 2. Result: cfg (immutable Settings) and info {value, auto, ceiling, source} → the “Computed by MINT” block.",
    "limits_warnings() предупреждение в «Модели и лимиты», если значение больше потолка или модели не хватает места.":
        "limits_warnings()\na warning in “Models and limits” if a value is above the ceiling or the model lacks room.",
    "ask_llm() при каждом вызове если окно LLM известно (сервер, config.yaml или панель): оценивает запрос в токенах; свободно < 256 ток. — ошибка «КОНТЕКСТ НЕ ПОМЕЩАЕТСЯ»; ответу мало места — max_tokens уменьшается. При типовом окне запрос не проверяется.":
        "ask_llm() on every call\nif the LLM window is known (server, config.yaml or sidebar): estimates the request in tokens; free < 256 tok. — error “CONTEXT DOES NOT FIT”; little room for the answer — max_tokens is reduced. With the typical window the request is not checked.",
    "ПРИОРИТЕТ ИСТОЧНИКОВ — один для всех параметров (его применяют resolve_model_limits() и resolve_settings()) • подключения (адреса, ключи, модели, папки): переменные окружения системы > .env • лимиты моделей: панель (сеанс) > config.yaml > сервер / измерение > типовое значение • остальные параметры: панель (сеанс) > config.yaml > расчёт MINT (для [А]) > умолчание в коде Явно заданное значение (панель или config.yaml) всегда важнее найденного у сервера и рассчитанного. [А]-параметр, зафиксированный вручную, MINT не пересчитывает, но предупредит, если он больше потолка модели (limits_warnings).":
        "SOURCE PRECEDENCE — the same for all parameters\n(applied by resolve_model_limits() and resolve_settings())\n\n• connections (addresses, keys, models, folders): system environment variables > .env\n• model limits: sidebar (session) > config.yaml > server / measurement > typical value\n• other parameters: sidebar (session) > config.yaml > MINT's calculation (for [A]) > default in code\n\nAn explicitly set value (sidebar or config.yaml) always wins over what the server reports and what is computed. An [A] parameter pinned by hand is not recomputed, but MINT warns if it is above the model's ceiling (limits_warnings).",
    "2. Как делится окно модели: что занимает место и сколько остаётся тексту из базы":
        "2. How the model window is divided: what takes room and how much is left for text from the base",
    "Слева — общий вид (масштаб условный), справа — те же полосы на числах: окно LLM 32768 ток., max_tokens 1500, chars_per_token 2.5, top_k 5, вход эмбеддингов и реранкера 8192 ток., Qwen3-Embedding. Узкие части на правых полосах показаны шире, чем в масштабе. Формула каждой части — колонка «Ограничения» в панели 3.":
        "Left — the general view (not to scale), right — the same bars with numbers: LLM window 32768 tok., max_tokens 1500, chars_per_token 2.5, top_k 5, embedding and reranker input 8192 tok., Qwen3-Embedding. Narrow parts on the right bars are drawn wider than to scale. The formula of each part — the “Constraints” column in panel 3.",
    "ОБЩИЙ ВИД":
        "GENERAL VIEW",
    "ПРИМЕР НА ЧИСЛАХ":
        "EXAMPLE WITH NUMBERS",
    "ЧАТ — один вызов LLM на вопрос. Вся полоса = llm_context_tokens [ток.]":
        "CHAT — one LLM call per question.  The whole bar = llm_context_tokens [tok.]",
    "ЧАТ, окно 32768 ток.":
        "CHAT, window 32768 tok.",
    "промпт, вопрос, история, сокращения CHAT_RESERVE 800 ток.":
        "prompt, question, history, abbreviations\nCHAT_RESERVE 800 tok.",
    "ответ max_tokens [ток.]":
        "answer\nmax_tokens [tok.]",
    "запас 15 % (× 0.85)":
        "margin 15 %\n(× 0.85)",
    "chat_budget остаток → в символы":
        "chat_budget\nthe rest → into characters",
    "промпт и пр. 800 ток.":
        "prompt etc.\n800 tok.",
    "ответ 1500 ток.":
        "answer\n1500 tok.",
    "запас 15 % 4 570 ток.":
        "margin 15 %\n4,570 tok.",
    "chat_budget 25 898 ток. × 2.5 = 64 744 симв.":
        "chat_budget\n25,898 tok. × 2.5 = 64,744 chars",
    "llm_context_tokens [ток.] — окно модели целиком":
        "llm_context_tokens [tok.] — the whole model window",
    "32 768 ток. = 800 + 1 500 + 4 570 + 25 898":
        "32,768 tok. = 800 + 1,500 + 4,570 + 25,898",
    "фрагмент 1 ≤ smart_truncate_chars":
        "fragment 1\n≤ smart_truncate_chars",
    "фрагмент 2":
        "fragment 2",
    "фрагмент top_k":
        "fragment top_k",
    "свободно, если фрагменты короче":
        "free if fragments are shorter",
    "свободно 52 244 симв. (значения ограничены умолчаниями)":
        "free 52,244 chars\n(values capped by the defaults)",
    "chat_budget [симв.] = top_k фрагментов + свободное место":
        "chat_budget [chars] = top_k fragments + free space",
    "64 744 симв.: 5 × 2500 = 12 500 занято, 52 244 свободно":
        "64,744 chars: 5 × 2500 = 12,500 used, 52,244 free",
    "ПОЧЕМУ 32768 ток. → ≈ 64 700 симв., А 4096 ток. → ЛИШЬ ≈ 3 800 симв. Из окна сначала вычитаются части фиксированного размера: ответ 1500 + промпт 800 = 2300 ток. Они одинаковы для любого окна: • 32768 − 2300 = 30 468 ток. × 2.5 × 0.85 = 64 744 симв. — фиксированные части заняли 7 % окна • 4096 − 2300 = 1 796 ток. × 2.5 × 0.85 = 3 816 симв. — фиксированные части заняли 56 % окна Окно меньше в 8 раз, а бюджет — в 17 раз.":
        "WHY 32768 tok. → ≈ 64,700 chars, BUT 4096 tok. → ONLY ≈ 3,800 chars\nParts of fixed size are subtracted from the window first: answer 1500 + prompt 800 = 2300 tok. They are the same for any window:\n• 32768 − 2300 = 30,468 tok. × 2.5 × 0.85 = 64,744 chars  — fixed parts took 7 % of the window\n• 4096 − 2300 = 1,796 tok. × 2.5 × 0.85 = 3,816 chars  — fixed parts took 56 % of the window\nThe window is 8 times smaller, the budget 17 times.",
    "ЧАТ, окно 4096 ток. — то же самое на маленькой модели":
        "CHAT, window 4096 tok. — the same on a small model",
    "запас 269 ток.":
        "margin\n269 tok.",
    "chat_budget 1 527 ток. × 2.5 = 3 816 симв.":
        "chat_budget\n1,527 tok. × 2.5 = 3,816 chars",
    "3 816 симв. / 5 = 763 симв. на фрагмент: MINT уменьшит parent_size и smart_truncate_chars до 763 и покажет это в «MINT рассчитал»":
        "3,816 chars / 5 = 763 chars per fragment: MINT reduces parent_size and smart_truncate_chars to 763 and shows it in “Computed by MINT”",
    "АУДИТ ДОКУМЕНТА — один вызов LLM (проверка одного раздела). Вся полоса = llm_context_tokens [ток.]":
        "DOCUMENT REVIEW — one LLM call (review of one section).  The whole bar = llm_context_tokens [tok.]",
    "АУДИТ, окно 32768 ток.: chars(32768 − 1500) = 66 444 симв.":
        "REVIEW, window 32768 tok.: chars(32768 − 1500) = 66,444 chars",
    "запас 15 %":
        "margin\n15 %",
    "промпт с критериями AUDIT_RESERVE 3500 симв.":
        "prompt with criteria\nAUDIT_RESERVE 3500 chars",
    "раздел документа audit_map_size":
        "document section\naudit_map_size",
    "нормы из базы — целые parent audit_context_max_chars":
        "norms from the base —\nwhole parents\naudit_context_max_chars",
    "свободно":
        "free",
    "запас 4 690 ток.":
        "margin\n4,690 tok.",
    "промпт 3500 симв.":
        "prompt\n3500 chars",
    "раздел 4500 симв.":
        "section\n4500 chars",
    "нормы ≤ 9000 симв. (≈ 3 целых parent)":
        "norms ≤ 9000 chars\n(≈ 3 whole\nparents)",
    "свободно 49 444 симв.":
        "free\n49,444 chars",
    "llm_budget [симв.]":
        "llm_budget [chars]",
    "llm_budget = 66 444 − 3 500 = 62 944 симв.":
        "llm_budget = 66,444 − 3,500 = 62,944 chars",
    "КОНТРОЛЬ ИСПРАВЛЕНИЙ — один вызов LLM на замечание. Вся полоса = llm_context_tokens [ток.]":
        "VERIFICATION OF FIXES — one LLM call per comment.  The whole bar = llm_context_tokens [tok.]",
    "КОНТРОЛЬ, окно 32768 ток.":
        "VERIFICATION, window 32768 tok.",
    "ответ max_tokens":
        "answer\nmax_tokens",
    "замечание ≈ 1000 симв.":
        "comment\n≈ 1000 chars",
    "нормы — целые parent audit_context_max_chars":
        "norms —\nwhole parents\naudit_context_max_chars",
    "разделы новой редакции review_context_max_chars":
        "sections of the new revision\nreview_context_max_chars",
    "промпт 3500":
        "prompt\n3500",
    "замечание 1000":
        "comment\n1000",
    "нормы ≤ 9000":
        "norms\n≤ 9000",
    "разделы 12 000 симв.":
        "sections\n12,000 chars",
    "свободно 40 944 симв.":
        "free\n40,944 chars",
    "ЭМБЕДДИНГИ — один child при индексации. Вся полоса = embed_max_tokens [ток.]":
        "EMBEDDINGS — one child at indexing.  The whole bar = embed_max_tokens [tok.]",
    "ЭМБЕДДИНГИ, вход 8192 ток.: chars(8192) = 17 408 симв.":
        "EMBEDDINGS, input 8192 tok.: chars(8192) = 17,408 chars",
    "путь заголовков 250 симв.":
        "heading path\n250 chars",
    "префикс документа":
        "document\nprefix",
    "child_size [симв.]":
        "child_size [chars]",
    "запас 1 229 ток.":
        "margin\n1,229 tok.",
    "заголовки 250":
        "headings\n250",
    "префикс 0 (Qwen3)":
        "prefix\n0 (Qwen3)",
    "свободно 16 758 симв.":
        "free 16,758 chars",
    "Такой же вход у раздела документа при подборе разделов (section_embed_chars) и у запроса аудита (audit_query_chars) — числа справа.":
        "A document section when matching sections (section_embed_chars) and a review query (audit_query_chars) have the same input — numbers on the right.",
    "Раздел: 0 + 4000 симв.; запрос аудита: префикс 171 симв. + 2000 — всё помещается в 17 408. Модель с входом 512 ток. → 1 088 симв.: child 400 ещё помещается, section_embed_chars уменьшится до 1 088.":
        "Section: 0 + 4000 chars; review query: prefix 171 chars + 2000 — everything fits into 17,408. A model with a 512-tok. input → 1,088 chars: child 400 still fits, section_embed_chars drops to 1,088.",
    "РЕРАНКЕР — одна пара «запрос + документ». Вся полоса = rerank_max_tokens [ток.]":
        "RERANKER — one “query + document” pair.  The whole bar = rerank_max_tokens [tok.]",
    "РЕРАНКЕР, вход 8192 ток.: chars(8192) = 17 408 симв.":
        "RERANKER, input 8192 tok.: chars(8192) = 17,408 chars",
    "запрос + сокращения rerank_query_max_chars":
        "query + abbreviations\nrerank_query_max_chars",
    "документ с именем файла и разделом rerank_doc_max_chars":
        "document with file name and section\nrerank_doc_max_chars",
    "запрос 1500":
        "query\n1500",
    "документ 800":
        "document\n800",
    "свободно 15 108 симв.":
        "free 15,108 chars",
    "Что получится при разных моделях (EMBED_MODEL = Qwen3-Embedding, top_k = 5); значения — [симв.]":
        "What you get with different models (EMBED_MODEL = Qwen3-Embedding, top_k = 5); values in [chars]",
    "Параметр":
        "Parameter",
    "Столбцы: окно LLM / вход эмбеддингов / вход реранкера, [ток.]; символов на токен 2.5 (в последнем — 3.0). ★ — типовые лимиты: значения совпадают с умолчаниями. ⚠ — модели не хватает места: MINT берёт минимум и показывает предупреждение. ▼ — сильно урезано: контроль исправлений видит малую часть новой редакции, вероятны ложные «не исправлено». 128k даёт те же значения, что 32k: умолчания — потолок (правило — панель 1).":
        "Columns: LLM window / embedding input / reranker input, [tok.]; characters per token 2.5 (in the last one 3.0). ★ — typical limits: the values equal the defaults. ⚠ — the model lacks room: MINT takes the minimum and shows a warning. ▼ — heavily cut: verification of fixes sees a small part of the new revision, false “not fixed” are likely. 128k gives the same values as 32k: the defaults are the ceiling (rule — panel 1).",
    "БОЛЬШОЕ ОКНО LLM (200k, 1M …) — ЧТО ТОГДА Предела окна в MINT нет (поле в панели принимает до 4 млн токенов). Большое окно поднимает потолки, но значения не выше умолчаний: в чат уходит ≈ top_k × 2500 симв., в аудит — раздел 4500 и нормы до 9000 симв. (3–4 целых parent). Так задумано: лишний контекст добавляет шум, время и стоимость, а точность от него обычно не растёт. Чтобы использовать большое окно — поднять вручную в config.yaml: • больше фрагментов в чате: top_k 8–12 → [Т] прогоны --k 5 / 8 / 12 и [П] живая проверка ответов • больше норм в аудите: audit_context_max_chars 13 000 (5 целых parent) … 20 000+; крупнее разделы: audit_map_size 12 000–30 000 (меньше вызовов, модель видит больше документа сразу) → [П] на документах с известными замечаниями • контроль исправлений: review_top_sections 5–8, review_context_max_chars 30 000+; длинные ответы — max_tokens • parent_size ♻ обычно не трогать: больше контекста лучше набирать числом фрагментов (top_k) Окно LLM не влияет на эмбеддинги и реранкер — у них свои лимиты.":
        "A LARGE LLM WINDOW (200k, 1M …) — WHAT THEN\nMINT has no window limit (the sidebar field accepts up to 4 million tokens). A large window raises the ceilings, but values stay at the defaults: chat gets ≈ top_k × 2500 chars, review — a 4500-char section and norms up to 9000 chars (3–4 whole parents). This is intended: extra context adds noise, time and cost, and accuracy usually does not grow.\n\nTo use a large window, raise values by hand in config.yaml:\n• more fragments in chat: top_k 8–12 → [T] runs with --k 5 / 8 / 12 and [C] a live check of answers\n• more norms in review: audit_context_max_chars 13,000 (5 whole parents) … 20,000+; larger sections: audit_map_size 12,000–30,000 (fewer calls, the model sees more of the document at once) → [C] on documents with known findings\n• verification of fixes: review_top_sections 5–8, review_context_max_chars 30,000+; long answers — max_tokens\n• parent_size ♻ usually leave as is: more context is better gained through the number of fragments (top_k)\n\nThe LLM window does not affect embeddings and the reranker — they have their own limits.",
    "3. Справочник параметров: определения, значения, ограничения":
        "3. Parameter reference: definitions, values, constraints",
    "Единицы: ток. — токены, симв. — символы. «В панели» — диапазон ползунка (если значение из config.yaml больше, ползунок расширяется). config.yaml проверяет только тип значения; защита от несовместимых значений — в коде (колонка «Ограничения»).":
        "Units: tok. — tokens, chars — characters. “Sidebar” — the slider range (if the value from config.yaml is larger, the slider widens). config.yaml checks only the value type; protection against incompatible values is in the code (the “Constraints” column).",
    "КАК ЧИТАТЬ «0 = авто: ① сервер ② иначе 32768 ток.» Это шаги по порядку: что стоит в коде → откуда MINT берёт значение. • 0 — значение в коде и в config.yaml по умолчанию: «не задано — определить автоматически». Ноль, а не число, нужен, чтобы MINT отличал «администратор ничего не указал» от явного значения (приоритет — панель 1). • ① сервер — первый шаг: MINT спрашивает лимит у сервера модели (detect_server_info, панель 1). Ответил — берётся это число; в «Модели и лимиты» видно «Сервер: …». • ② иначе 32768 — сервер не сообщил (часто у корпоративных шлюзов и облачных API): берётся типовое значение — безопасная догадка (почему именно такое — справа). Типовое значение может не совпасть с вашей моделью: при нём MINT размер запроса не проверяет. Чем грозит ошибка — строка llm_context_tokens; лимит лучше указать вручную (панель или config.yaml).":
        "HOW TO READ “0 = auto: ① server ② otherwise 32768 tok.”\nThese are steps in order: what is in the code → where MINT takes the value from.\n• 0 — the value in the code and in config.yaml by default: “not set — detect automatically”. Zero rather than a number lets MINT tell “the administrator set nothing” from an explicit value (precedence — panel 1).\n• ① server — the first step: MINT asks the model server for the limit (detect_server_info, panel 1). If it answers, that number is used; “Models and limits” shows “Server: …”.\n• ② otherwise 32768 — the server did not report it (common for corporate gateways and cloud APIs): the typical value is used — a safe guess (why exactly this one — on the right).\nThe typical value may not match your model: with it MINT does not check the request size. What an error leads to — the llm_context_tokens row; better set the limit by hand (sidebar or config.yaml).",
    "ПОЧЕМУ ИМЕННО ЭТИ ТИПОВЫЕ ЗНАЧЕНИЯ (FALLBACK_LIMITS) • окно LLM 32768 ток. — обычное окно открытых моделей при развёртывании (Qwen2.5 / Qwen3, Llama 3.x, Mistral на vLLM); почти все современные модели не меньше. • вход эмбеддингов 8192 ток. — Qwen3-Embedding, bge-m3, gte-Qwen; модели на 512 ток. — см. embed_max_tokens. • вход реранкера 8192 ток. — bge-reranker-v2-m3. • 2.5 симв./ток. — см. блок «Токены и символы» вверху. ЧИСЛО У [А]-ПАРАМЕТРА (например, 3500 симв.) Это умолчание. Расчёт может только уменьшить его под маленькую модель (формула — колонка «Ограничения»), но не увеличивает.":
        "WHY THESE TYPICAL VALUES (FALLBACK_LIMITS)\n• LLM window 32768 tok. — the usual window of open models when deployed (Qwen2.5 / Qwen3, Llama 3.x, Mistral on vLLM); almost all modern models have at least this.\n• embedding input 8192 tok. — Qwen3-Embedding, bge-m3, gte-Qwen; 512-tok. models — see embed_max_tokens.\n• reranker input 8192 tok. — bge-reranker-v2-m3.\n• 2.5 chars/tok. — see the “Tokens and characters” block at the top.\n\nTHE NUMBER OF AN [A] PARAMETER (for example, 3500 chars)\nThis is the default. The calculation can only reduce it for a small model (formula — the “Constraints” column), never increase it.",
    "Что это":
        "What it is",
    "По умолчанию":
        "Default",
    "В панели":
        "Sidebar",
    "Ограничения и зависимости":
        "Constraints and dependencies",
    "ПОДКЛЮЧЕНИЯ — .env":
        "CONNECTIONS — .env",
    "Базовый адрес OpenAI-совместимого API языковой модели (…/v1); к нему добавляются /chat/completions и /models.":
        "Base address of the OpenAI-compatible API of the language model (…/v1); /chat/completions and /models are appended to it.",
    "— (обязательно)":
        "— (required)",
    "Пусто — ошибка в панели: чат, аудит и контроль не работают.":
        "Empty — an error in the sidebar: chat, review and verification do not work.",
    "Полный адрес эндпоинта эмбеддингов (…/v1/embeddings).":
        "Full address of the embeddings endpoint (…/v1/embeddings).",
    "Пусто — загрузка документов невозможна, поиск только по словам (BM25).":
        "Empty — documents cannot be uploaded, search uses words only (BM25).",
    "Полный адрес реранкера (…/v1/rerank).":
        "Full address of the reranker (…/v1/rerank).",
    "пусто — без реранкера":
        "empty — no reranker",
    "Необязателен: без него порядок задают векторный поиск и BM25.":
        "Optional: without it the order is set by vector search and BM25.",
    "Ключи доступа (Bearer).":
        "Access keys (Bearer).",
    "пусто":
        "empty",
    "Пустые EMBED_ / RERANK_ — берётся LLM_API_KEY; пустой LLM_API_KEY — запросы без авторизации.":
        "Empty EMBED_ / RERANK_ — LLM_API_KEY is used; empty LLM_API_KEY — requests without authorisation.",
    "Модель по умолчанию в списке «Модель ИИ» (старое имя — DEFAULT_LLM_MODEL).":
        "Default model in the “AI model” list (old name — DEFAULT_LLM_MODEL).",
    "первая из списка сервера":
        "the first one listed by the server",
    "список моделей":
        "model list",
    "Список запрашивается у сервера; модель из .env добавляется в список, даже если сервер её не вернул.":
        "The list is requested from the server; the model from .env is added to it even if the server did not return it.",
    "Модель эмбеддингов; записывается в manifest каждого документа.":
        "Embedding model; recorded in the manifest of every document.",
    "Смена — переиндексация; другая размерность векторов — векторный поиск выключается до переиндексации.":
        "Changing it — re-indexing; a different vector dimension — vector search is off until re-indexing.",
    "Модель реранкера.":
        "Reranker model.",
    "Сертификат для TLS; SSL_INSECURE = 1 отключает проверку.":
        "TLS certificate; SSL_INSECURE = 1 turns verification off.",
    "системный файл сертификатов (Windows — хранилище Windows); выкл.":
        "system certificate file (Windows — the Windows store); off",
    "Файла нет — системные сертификаты; на Windows — через truststore. SSL_INSECURE — только во внутренней сети.":
        "No file — system certificates; on Windows via truststore. SSL_INSECURE — only in an internal network.",
    "Папка базы, папка логов и отзывов, путь к glossary.json и к config.yaml.":
        "Knowledge base folder, folder for logs and feedback, paths to glossary.json and config.yaml.",
    "~/knowledge_base; ~/mint_logs; рядом с программой":
        "~/knowledge_base; ~/mint_logs; next to the program",
    "Лог — mint_system.log с ротацией 10 МБ × 5; отзывы пользователей — feedback.jsonl.":
        "Log — mint_system.log rotated at 10 MB × 5; user feedback — feedback.jsonl.",
    "Язык интерфейса, промптов и отчётов: ru или en.":
        "Language of the interface, prompts and reports: en or ru.",
    "язык ОС (ru → ru, иначе en)":
        "OS language (ru → ru, otherwise en)",
    "переключатель в панели":
        "switch in the sidebar",
    "Переключатель меняет язык на сеанс; check_install.py тоже пишет на этом языке.":
        "The switch changes the language for the session; check_install.py writes in this language too.",
    "ЛИМИТЫ МОДЕЛЕЙ — config.yaml, раздел models":
        "MODEL LIMITS — config.yaml, the models section",
    "Окно контекста LLM, токенов: всё, что модель принимает за один вызов — промпт + найденные фрагменты + история + ответ.":
        "LLM context window, tokens: everything the model takes in one call — prompt + retrieved fragments + history + answer.",
    "0 = авто: ① сервер (/models) ② иначе 32768 ток.":
        "0 = auto:\n① server (/models)\n② otherwise 32768 tok.",
    "128 … 4 млн":
        "128 … 4 million",
    "Предела сверху нет. От него: chat_budget, llm_budget — а через них потолки smart_truncate_chars, parent_size, audit_map_size, audit_context_max_chars, review_context_max_chars.":
        "No upper limit. Depending on it: chat_budget, llm_budget — and through them the ceilings of smart_truncate_chars, parent_size, audit_map_size, audit_context_max_chars, review_context_max_chars.",
    "Подробнее: главный лимит MINT. Указывайте то, что реально пропускает сервер: если шлюз режет запросы раньше окна модели — предел шлюза. Ошибка в бо́льшую сторону опаснее: MINT посчитает, что всё помещается, а сервер вернёт «ОШИБКА ШЛЮЗА: код 400» (vLLM) или молча обрежет начало промпта (Ollama). Ошибка в меньшую — только фрагменты короче, чем можно.":
        "Details: MINT's main limit. Set what the server actually accepts: if the gateway cuts requests before the model window — the gateway's limit. An error upwards is more dangerous: MINT assumes everything fits, and the server returns “GATEWAY ERROR: code 400” (vLLM) or silently cuts the start of the prompt (Ollama). An error downwards only makes fragments shorter than they could be.",
    "Максимальная длина входа модели эмбеддингов, токенов.":
        "Maximum input length of the embedding model, tokens.",
    "0 = авто: ① сервер (/models) ② иначе 8192 ток.":
        "0 = auto:\n① server (/models)\n② otherwise 8192 tok.",
    "От него: child_size ♻, section_embed_chars, audit_query_chars, embed_input_max_chars.":
        "Depending on it: child_size ♻, section_embed_chars, audit_query_chars, embed_input_max_chars.",
    "Подробнее: для моделей с входом 512 токенов (e5, ruBERT и другие BERT-подобные) обязательно указать 512, если сервер не сообщает: иначе MINT будет считать, что вход 8192, и отправлять разделы по 4000 симв. (≈ 1600 токенов) — сервер их обрежет или вернёт ошибку. Смена значения меняет child_size — нужна переиндексация ♻.":
        "Details: for models with a 512-token input (e5, ruBERT and other BERT-like ones) be sure to set 512 if the server does not report it: otherwise MINT assumes an 8192 input and sends 4000-char sections (≈ 1600 tokens) — the server cuts them or returns an error. Changing the value changes child_size — re-indexing is needed ♻.",
    "Максимальная длина пары «запрос + документ» у реранкера, токенов.":
        "Maximum length of a “query + document” pair for the reranker, tokens.",
    "От него: rerank_query_max_chars, rerank_doc_max_chars.":
        "Depending on it: rerank_query_max_chars, rerank_doc_max_chars.",
    "Сколько символов текста приходится на один токен; переводит лимиты моделей из токенов в символы.":
        "How many characters of text make one token; converts model limits from tokens to characters.",
    "0 = авто: ① измерение кнопкой ② иначе 2.5 симв./ток.":
        "0 = auto:\n① measured by the button\n② otherwise 2.5 chars/tok.",
    "Измерение принимается в пределах 1 … 8. Как измеряется и какие значения обычны — блок «Токены и символы» вверху.":
        "A measurement is accepted within 1 … 8. How it is measured and which values are typical — the “Tokens and characters” block at the top.",
    "Подробнее: участвует во всех формулах, где лимит модели переводится в символы. Меньше реального — MINT перестраховывается (фрагменты короче, чем можно). Больше реального — запросы могут не поместиться в модель.":
        "Details: used in every formula where a model limit is converted to characters. Lower than real — MINT plays safe (fragments shorter than they could be). Higher than real — requests may not fit into the model.",
    "Инструкция перед текстом запроса для моделей эмбеддингов с инструкцией.":
        "Instruction before the query text for embedding models trained with instructions.",
    "по имени модели":
        "by model name",
    "только config.yaml":
        "config.yaml only",
    "Уменьшает audit_query_chars на свою длину. Смена переиндексации не требует.":
        "Reduces audit_query_chars by its length. Changing it does not require re-indexing.",
    "Подробнее: что это: многие модели эмбеддингов обучены на парах «вопрос — документ», где вопрос помечен особой фразой. Без пометки такая модель ищет заметно хуже (вопрос и документ «звучат» для неё одинаково). Откуда берётся: embed_prefix_preset() сравнивает имя EMBED_MODEL с таблицей EMBED_PREFIX_PRESETS — Qwen3-Embedding, gte-Qwen, e5-instruct → «Instruct: <задача поиска>\\nQuery:» (171 симв.; задача — константа EMBED_TASK: «найти фрагменты регламентов и архитектурных документов, относящиеся к вопросу или фрагменту проверяемого документа»); e5 → «query: »; nomic-embed, FRIDA, ru-en-RoSBERTa → «search_query: »; bge-m3 и все остальные → без префикса. Значение из config.yaml важнее таблицы. Где применяется: вопрос чата, начало раздела документа при поиске норм (аудит), замечание при подборе разделов (контроль). Что выбрано — видно в «Модели и лимиты»: «Префикс запроса для модели эмбеддингов (…)».":
        "Details: what it is: many embedding models are trained on “question — document” pairs where the question is marked with a special phrase. Without the mark such a model searches noticeably worse (question and document “sound” the same to it). Where it comes from: embed_prefix_preset() matches the EMBED_MODEL name against the EMBED_PREFIX_PRESETS table — Qwen3-Embedding, gte-Qwen, e5-instruct → “Instruct: <search task>\\nQuery:” (171 chars; the task is the EMBED_TASK constant: “Given a question or a fragment of a document under review, retrieve passages from corporate regulations and architecture documents that are relevant to it”); e5 → “query: ”; nomic-embed, FRIDA, ru-en-RoSBERTa → “search_query: ”; bge-m3 and all others → no prefix. A value from config.yaml wins over the table. Where it is used: the chat question, the start of a document section when searching for norms (review), a comment when matching sections (verification). What was chosen is shown in “Models and limits”: “Query prefix for the embedding model (…)”.",
    "Префикс перед текстом документа (e5, nomic, FRIDA).":
        "Prefix before the document text (e5, nomic, FRIDA).",
    "Смена — переиндексация (сравнивается с manifest). Уменьшает child_size и section_embed_chars.":
        "Changing it — re-indexing (compared with the manifest). Reduces child_size and section_embed_chars.",
    "Подробнее: пара к префиксу запроса — пометка текста документа: e5 → «passage: », nomic, FRIDA, RoSBERTa → «search_document: »; Qwen3-Embedding и bge-m3 — без префикса (у Qwen3 инструкция только у запроса). Добавляется к каждому child при индексации и к разделам новой редакции на вкладке контроля. Если модель на шлюзе названа по-своему (например, «emb-prod») и не распознана — оба префикса пустые: задайте их в config.yaml по документации модели и сравните проверкой качества до и после.":
        "Details: the pair of the query prefix — a mark for document text: e5 → “passage: ”, nomic, FRIDA, RoSBERTa → “search_document: ”; Qwen3-Embedding and bge-m3 — no prefix (Qwen3 has an instruction only for the query). Added to every child at indexing and to the sections of the new revision on the verification tab. If the model on the gateway has its own name (for example, “emb-prod”) and is not recognised, both prefixes are empty: set them in config.yaml from the model's documentation and compare with a quality check before and after.",
    "ПРОМЕЖУТОЧНЫЕ ВЕЛИЧИНЫ — рассчитываются в _derive(), не задаются: меняются через лимиты моделей и max_tokens":
        "INTERMEDIATE VALUES — computed in _derive(), not set: changed through model limits and max_tokens",
    "Бюджет контекста чата: сколько символов найденных фрагментов помещается в окно LLM при ответе в чате — после того как из окна вычтено место под ответ и под промпт, вопрос и историю.":
        "Chat context budget: how many characters of retrieved fragments fit into the LLM window for a chat answer — after room for the answer, the prompt, the question and the history is subtracted from the window.",
    "≈ 64 700 симв. (окно 32768, ответ 1500)":
        "≈ 64,700 chars\n(window 32768, answer 1500)",
    "не задаётся":
        "not set",
    "= chars(llm_context_tokens − max_tokens − 800); 800 ток. — CHAT_RESERVE_TOKENS (промпт, вопрос, история). От него: smart_truncate_chars, parent_size.":
        "= chars(llm_context_tokens − max_tokens − 800); 800 tok. — CHAT_RESERVE_TOKENS (prompt, question, history). Depending on it: smart_truncate_chars, parent_size.",
    "Подробнее: увеличить бюджет можно бо́льшим окном (если модель позволяет) или меньшим max_tokens. Почему окно 4096 даёт бюджет в 17 раз меньше, чем 32768, — разбор на числах в панели 2.":
        "Details: the budget can be increased with a larger window (if the model allows) or a smaller max_tokens. Why a 4096 window gives a budget 17 times smaller than 32768 — worked through with numbers in panel 2.",
    "Бюджет контекста аудита и контроля исправлений: сколько символов (раздел документа + нормы из базы + разделы новой редакции) помещается в окно LLM.":
        "Context budget of review and verification of fixes: how many characters (document section + norms from the base + sections of the new revision) fit into the LLM window.",
    "≈ 62 900 симв. (окно 32768, ответ 1500)":
        "≈ 62,900 chars\n(window 32768, answer 1500)",
    "= chars(llm_context_tokens − max_tokens) − 3500; 3500 симв. — AUDIT_RESERVE_CHARS (промпт с критериями). От него: audit_map_size, audit_context_max_chars, review_context_max_chars.":
        "= chars(llm_context_tokens − max_tokens) − 3500; 3500 chars — AUDIT_RESERVE_CHARS (prompt with criteria). Depending on it: audit_map_size, audit_context_max_chars, review_context_max_chars.",
    "Предельная длина текста, отправляемого в модель эмбеддингов; длиннее — обрезается перед отправкой (_embed_input).":
        "Maximum length of text sent to the embedding model; longer text is cut before sending (_embed_input).",
    "≈ 17 400 симв. (вход 8192)":
        "≈ 17,400 chars\n(input 8192)",
    "= chars(embed_max_tokens). Страховка: ни один запрос к эмбеддингам не превысит вход модели.":
        "= chars(embed_max_tokens). A safeguard: no embedding request exceeds the model input.",
    "ЯЗЫКОВАЯ МОДЕЛЬ":
        "LANGUAGE MODEL",
    "Случайность ответа LLM.":
        "Randomness of the LLM answer.",
    "Действует на ответы чата, аудит, самокритику аудита и контроль исправлений. Исключение — служебный шаг чата condense_question(): уточняющий вопрос («а для второго контура?») переписывается в самостоятельный всегда с temperature 0, чтобы поиск получал одну и ту же формулировку. К самокритике это не относится.":
        "Applies to chat answers, review, review self-critique and verification of fixes. The exception is the chat's service step condense_question(): a follow-up question (“and for the second circuit?”) is always rewritten into a self-contained one with temperature 0, so that search gets the same wording. Self-critique is not affected by this.",
    "Максимальная длина ответа модели, токенов.":
        "Maximum length of the model answer, tokens.",
    "1500 ток.":
        "1500 tok.",
    "От него: chat_budget, llm_budget.":
        "Depending on it: chat_budget, llm_budget.",
    "Подробнее: место под ответ резервируется в окне заранее, даже если ответ окажется коротким: каждые +1000 ток. ответа отнимают ≈ 2 100 симв. у chat_budget и llm_budget. На окне 32k это незаметно, на 4–8k — существенно. Модели с рассуждениями — панель 4.":
        "Details: room for the answer is reserved in the window in advance, even if the answer turns out short: every +1000 tok. of answer take ≈ 2,100 chars from chat_budget and llm_budget. On a 32k window this is unnoticeable, on 4–8k it matters. Reasoning models — panel 4.",
    "Ожидание ответа LLM на одну попытку, сек.":
        "Wait for an LLM answer per attempt, s.",
    "Истёк — следующая попытка (llm_retries).":
        "On timeout — the next attempt (llm_retries).",
    "Число попыток при таймауте и 502 / 503 / 504; на 429 — не меньше 4, с общей паузой.":
        "Number of attempts on timeout and 502 / 503 / 504; on 429 at least 4, with a shared pause.",
    "Пауза растёт: ≈ 2 с, 4 с … (+ случайная); 401 / 403 — сразу ошибка.":
        "The pause grows: ≈ 2 s, 4 s … (+ random); 401 / 403 — an error at once.",
    "Ожидание ответа реранкера, сек.":
        "Wait for a reranker answer, s.",
    "ИНДЕКСАЦИЯ ♻":
        "INDEXING ♻",
    "Длина parent-фрагмента: его читает LLM.":
        "Length of a parent fragment: the LLM reads it.",
    "2500 симв.":
        "2500 chars",
    "Авто ≤ chat_budget / 5 (минимум 300). В коде не меньше 200. От него: parent_overlap.":
        "Auto ≤ chat_budget / 5 (minimum 300). In the code at least 200. Depending on it: parent_overlap.",
    "Подробнее: parent — «единица чтения»: поиск находит маленький child, а модели отдаётся весь parent вокруг него, чтобы был контекст. Почему зависит от chat_budget: parent целиком идёт в контекст; длиннее своей доли бюджета — smart_truncate_chars обрежет его вокруг найденного места, и окружающий текст пропадёт. Делится на 5, а не на top_k: нарезка делается один раз при загрузке, а top_k меняется в каждом сеансе — 5 это типичный top_k. На окне 32k ограничение не срабатывает (64 744 / 5 = 12 949 > 2500), на 4k срабатывает (→ 763). Больше parent — меньше разрывов смысла, но больше шума и меньше разных мест в том же бюджете. Режется по тексту — сначала по границе абзаца, затем строки, предложения и слова; заголовок не отрывается от своего текста. Один parent может захватить конец одного раздела и начало другого.":
        "Details: a parent is the “unit of reading”: search finds a small child, and the model gets the whole parent around it for context. Why it depends on chat_budget: the whole parent goes into the context; if it is longer than its share of the budget, smart_truncate_chars cuts it around the match and the surrounding text is lost. Divided by 5, not by top_k: chunking happens once at upload, while top_k changes in every session — 5 is the typical top_k. On a 32k window the limit does not apply (64,744 / 5 = 12,949 > 2500), on 4k it does (→ 763). A larger parent — fewer breaks in meaning, but more noise and fewer different places in the same budget. Cut along the text — first at a paragraph break, then at a line, a sentence and a word; a heading is not separated from its text. One parent can take the end of one section and the start of the next.",
    "Перекрытие соседних parent.":
        "Overlap of neighbouring parents.",
    "300 симв.":
        "300 chars",
    "Авто ≤ parent_size / 5; в коде меньше parent_size.":
        "Auto ≤ parent_size / 5; in the code less than parent_size.",
    "Длина child-фрагмента — единицы векторного поиска.":
        "Length of a child fragment — the unit of vector search.",
    "400 симв.":
        "400 chars",
    "Авто ≤ вход эмбеддингов − 250 − префикс документа (минимум 100); 250 — путь заголовков (HEADING_RESERVE_CHARS); в коде от 50 до parent_size. От него: child_overlap.":
        "Auto ≤ embedding input − 250 − document prefix (minimum 100); 250 — the heading path (HEADING_RESERVE_CHARS); in the code from 50 to parent_size. Depending on it: child_overlap.",
    "Подробнее: child — «единица поиска»: по нему считается вектор. Короткий child точнее совпадает с вопросом, длинный — размывается. 400 симв. (≈ 2–4 предложения) — компромисс для регламентов.":
        "Details: a child is the “unit of search”: the vector is computed from it. A short child matches a question more precisely, a long one gets blurred. 400 chars (≈ 2–4 sentences) is a compromise for regulations.",
    "Перекрытие соседних child.":
        "Overlap of neighbouring children.",
    "150 симв.":
        "150 chars",
    "Авто ≤ child_size / 2; в коде меньше child_size.":
        "Auto ≤ child_size / 2; in the code less than child_size.",
    "Текстов в одном запросе эмбеддингов при индексации.":
        "Texts per embedding request at indexing.",
    "Не меньше 1; предел — сервер эмбеддингов. Сбой пачки — по одному.":
        "At least 1; the limit is the embedding server. A failed batch — one by one.",
    "ПОИСК":
        "SEARCH",
    "Сколько найденных фрагментов (parent) MINT кладёт в контекст LLM при ответе в чате. Тот же top_k берут аудит документа (нормы из базы) и контроль исправлений.":
        "How many retrieved fragments (parents) MINT puts into the LLM context for a chat answer. Document review (norms from the base) and verification of fixes use the same top_k.",
    "0 = авто: 4, если в базе ≤ 300 child 5, если больше":
        "0 = auto:\n4 if the base has ≤ 300 children\n5 if more",
    "Не больше rerank_top_k (отбор идёт из этих кандидатов). Сверху в коде не ограничен: больше 8 — через config.yaml. От него: smart_truncate_chars.":
        "At most rerank_top_k (selection is made from these candidates). No upper limit in the code: above 8 — through config.yaml. Depending on it: smart_truncate_chars.",
    "Подробнее: в коде top_k = 0, то есть «выбрать автоматически»: MINT считает child-фрагменты в базе (kb_default_top_k). ≤ 300 (≈ 10–15 регламентов) → 4: пятый фрагмент обычно повтор или шум; больше → 5: ответ чаще разбросан по нескольким местам. Ползунок «Глубина поиска (Top-K)» стоит на авто-значении и меняет его на сеанс; config.yaml (search: top_k: 6) отключает автоматику. Связь с лимитами: фрагменты делят бюджет окна — каждый обрезается до smart_truncate_chars ≈ (окно − ответ − резерв) / top_k. Больше top_k — модель видит больше разных мест, но каждое короче. На маленьком окне top_k 8 даст обрывки (под ползунком: «Контекст чата: до ≈ N симв. (Top-K × фрагмент)»); на большом фрагменты остаются полными. В аудите действует ещё и audit_context_max_chars. Как подбирать: начать с авто. Часто «информация отсутствует», а ответ в базе есть → смотреть hit@3 и hit@K в report.md: правильный фрагмент на 5–8 месте → поднять top_k до 6–8. Нет его и в первой десятке → top_k не поможет: проблема в поиске или нарезке.":
        "Details: in the code top_k = 0, i.e. “choose automatically”: MINT counts child fragments in the base (kb_default_top_k). ≤ 300 (≈ 10–15 regulations) → 4: a fifth fragment is usually a repeat or noise; more → 5: the answer is more often spread over several places. The “Search depth (Top-K)” slider starts at the auto value and changes it for the session; config.yaml (search: top_k: 6) turns the automation off.\nLink to the limits: fragments share the window budget — each is cut to smart_truncate_chars ≈ (window − answer − reserve) / top_k. A larger top_k — the model sees more different places, but each is shorter. On a small window top_k 8 gives scraps (under the slider: “Chat context: up to ≈ N chars (Top-K × fragment)”); on a large one fragments stay whole. In review audit_context_max_chars applies as well.\nHow to tune: start with auto. Often “the information is not available” although the answer is in the base → look at hit@3 and hit@K in report.md: the correct fragment at place 5–8 → raise top_k to 6–8. Not even in the top ten → top_k will not help: the problem is in search or chunking.",
    "Сколько ближайших child берёт векторный поиск.":
        "How many nearest children vector search takes.",
    "Не больше числа векторов в базе; несколько child одного parent дают одного кандидата.":
        "At most the number of vectors in the base; several children of one parent give one candidate.",
    "Сколько parent берёт поиск по словам.":
        "How many parents word search takes.",
    "Берутся только фрагменты с баллом > 0.":
        "Only fragments with a score > 0 are taken.",
    "Кандидатов после слияния: идут на реранк и в отбор top_k.":
        "Candidates after fusion: they go to reranking and to the top_k selection.",
    "Ограничивает top_k сверху. Больше — больше запросов к реранкеру.":
        "Caps top_k. More — more requests to the reranker.",
    "Константа сглаживания слияния RRF (формула — панель 7).":
        "Smoothing constant of RRF fusion (formula — panel 7).",
    "Меньше — сильнее разница между первыми местами списков.":
        "Smaller — a stronger difference between the first places of the lists.",
    "Вес векторного поиска в слиянии.":
        "Weight of vector search in the fusion.",
    "0 — канал отключён.":
        "0 — the channel is off.",
    "Вес поиска по словам в слиянии.":
        "Weight of word search in the fusion.",
    "Вес голоса реранкера в слиянии.":
        "Weight of the reranker's vote in the fusion.",
    "Только с реранкером. 0 — порядок без реранкера, его баллы остаются для «уверенность низкая».":
        "Only with a reranker. 0 — the order without the reranker, its scores still decide on “low confidence”.",
    "Подробнее: реранкер не заменяет порядок, а голосует в слиянии наравне с векторным поиском и BM25. 0.7 — реранкер чуть слабее каждого из двух поисков; 1.5–3 — его мнение решающее.":
        "Details: the reranker does not replace the order but votes in the fusion alongside vector search and BM25. 0.7 — the reranker is slightly weaker than each of the two searches; 1.5–3 — its opinion decides.",
    "Максимальная длина одного фрагмента в контексте LLM.":
        "Maximum length of one fragment in the LLM context.",
    "3500 симв. — или меньше, если не помещается":
        "3500 chars — or less\nif it does not fit",
    "Авто ≤ chat_budget / top_k (минимум 500). Длиннее — фрагмент обрезается вокруг найденного места (focus_passage); ближайший заголовок выше сохраняется, у таблицы — заголовок и шапка.":
        "Auto ≤ chat_budget / top_k (minimum 500). Longer — the fragment is cut around the match (focus_passage); the nearest heading above is kept, a table keeps its title and header.",
    "Подробнее: при умолчаниях (parent 2500 < 3500) ничего не обрезается — лимит срабатывает только на маленьком окне или большом top_k. Обрезается вокруг найденного места: child из векторного поиска или окно, где больше всего слов вопроса. Соседние фрагменты одного документа склеиваются в один блок (merge_adjacent) без повтора перекрытия; его лимит — smart_truncate_chars × число склеенных.":
        "Details: with the defaults (parent 2500 < 3500) nothing is cut — the limit applies only with a small window or a large top_k. Cut around the match: the child from vector search or the window with the most question words. Neighbouring fragments of one document are joined into one block (merge_adjacent) without repeating the overlap; its limit is smart_truncate_chars × the number joined.",
    "Сколько частей одной таблицы может попасть в контекст.":
        "How many parts of one table can get into the context.",
    "0 — без ограничения. Лимит мягкий: свободные места добираются частями.":
        "0 — no limit. A soft limit: free places are filled with parts.",
    "Вторая формулировка вопроса от LLM; кандидаты ищутся по обеим.":
        "A second wording of the question from the LLM; candidates are searched for both.",
    "выкл.":
        "off",
    "флажок":
        "checkbox",
    "Вопросы длиннее 1200 симв. не перефразируются.":
        "Questions longer than 1200 chars are not paraphrased.",
    "Вес результатов по второй формулировке.":
        "Weight of the results for the second wording.",
    "Максимальная длина запроса к поиску; длиннее — обрезается.":
        "Maximum length of a search query; longer is cut.",
    "24000 симв.":
        "24000 chars",
    "Запрос длиннее делится пополам и ищется частями.":
        "A longer query is split in half and searched in parts.",
    "20000 симв.":
        "20000 chars",
    "Глубина деления — не больше 3.":
        "Split depth — at most 3.",
    "РЕРАНКЕР — используются, только если задан RERANK_API_URL":
        "RERANKER — used only if RERANK_API_URL is set",
    "Документов в одном запросе к реранкеру.":
        "Documents per reranker request.",
    "Ограничение шлюза; остальные кандидаты — следующими запросами.":
        "A gateway limit; the remaining candidates go in the next requests.",
    "Символов в одном запросе к реранкеру.":
        "Characters per reranker request.",
    "9000 симв.":
        "9000 chars",
    "Ограничение шлюза; один документ уходит всегда, даже если длиннее.":
        "A gateway limit; one document is always sent, even if longer.",
    "Длина запроса (с расшифровками сокращений) для реранкера.":
        "Query length (with abbreviation expansions) for the reranker.",
    "1500 симв.":
        "1500 chars",
    "Авто ≤ вход реранкера / 3 (минимум 200). От него: rerank_doc_max_chars.":
        "Auto ≤ reranker input / 3 (minimum 200). Depending on it: rerank_doc_max_chars.",
    "Длина фрагмента документа для реранкера вместе с именем файла и разделом.":
        "Length of a document fragment for the reranker, including file name and section.",
    "800 симв.":
        "800 chars",
    "Авто ≤ вход реранкера − длина запроса (минимум 200); сам фрагмент не короче 150 симв.":
        "Auto ≤ reranker input − query length (minimum 200); the fragment itself at least 150 chars.",
    "Добавлять имя файла, раздел и таблицу в начало текста для реранкера.":
        "Add the file name, section and table to the start of the text for the reranker.",
    "вкл.":
        "on",
    "Минимальный балл, при котором голос реранкера учитывается.":
        "Minimum score at which the reranker's vote counts.",
    "Рассчитан на шкалу 0 … 1; у реранкера с другой шкалой — задать вручную.":
        "Designed for a 0 … 1 scale; for a reranker with a different scale set it by hand.",
    "СИГНАЛ «УВЕРЕННОСТЬ НИЗКАЯ» — как срабатывает, см. панель 7":
        "THE “LOW CONFIDENCE” SIGNAL — how it fires, see panel 7",
    "Порог лучшего балла реранкера.":
        "Threshold for the best reranker score.",
    "С реранкером сигнал зависит только от него.":
        "With a reranker the signal depends only on it.",
    "Только без реранкера: порог доли слов вопроса в контексте.":
        "Only without a reranker: threshold for the share of question words in the context.",
    "Слова сравниваются по основам; вопросительные слова не считаются.":
        "Words are compared by stems; question words are not counted.",
    "Только без реранкера: глубина совпадения векторного поиска и BM25.":
        "Only without a reranker: depth at which vector search and BM25 must agree.",
    "Показывать баллы и позиции рядом с источниками в чате.":
        "Show scores and positions next to sources in chat.",
    "ЧАТ И ГЛОССАРИЙ":
        "CHAT AND GLOSSARY",
    "Сколько прошлых пар «вопрос — ответ» учитывать для уточняющих вопросов.":
        "How many past “question — answer” pairs to use for follow-up questions.",
    "0 — без истории; ответ ассистента в истории обрезается до 1200 симв.":
        "0 — no history; the assistant's answer in the history is cut to 1200 chars.",
    "Собирать сокращения из загруженных документов.":
        "Collect abbreviations from uploaded documents.",
    "Передавать модели справочник найденных сокращений.":
        "Give the model a reference of the abbreviations found.",
    "Выключить, если автоглоссарий даёт ошибочные расшифровки.":
        "Turn off if the auto-glossary gives wrong expansions.",
    "Сокращений в справочнике для модели, не больше.":
        "Abbreviations in the model's reference, at most.",
    "Сначала сокращения из вопроса, затем из найденных фрагментов.":
        "First abbreviations from the question, then from the retrieved fragments.",
    "АУДИТ ДОКУМЕНТА И КОНТРОЛЬ ИСПРАВЛЕНИЙ":
        "DOCUMENT REVIEW AND VERIFICATION OF FIXES",
    "Размер раздела документа на одну проверку; тот же размер — у разделов на вкладке контроля.":
        "Size of a document section per review call; sections on the verification tab have the same size.",
    "4500 симв.":
        "4500 chars",
    "Авто ≤ 0.3 × llm_budget (минимум 1000). Меньше — детальнее, но больше вызовов LLM. От него: audit_context_max_chars.":
        "Auto ≤ 0.3 × llm_budget (minimum 1000). Smaller — more detailed, but more LLM calls. Depending on it: audit_context_max_chars.",
    "Второй проход «контролёр» по черновику замечаний.":
        "A second “controller” pass over the draft findings.",
    "Отсеивает надуманные замечания; без него быстрее.":
        "Filters out far-fetched findings; faster without it.",
    "Сколько символов начала раздела уходит в поиск норм.":
        "How many characters from the start of a section go into the search for norms.",
    "2000 симв.":
        "2000 chars",
    "Авто ≤ вход эмбеддингов − префикс запроса (минимум 300).":
        "Auto ≤ embedding input − query prefix (minimum 300).",
    "Сколько текста норм из базы (parent целиком, суммарно) попадает в проверку одного раздела документа.":
        "How much norm text from the base (whole parents, in total) goes into the review of one document section.",
    "Авто ≤ llm_budget − audit_map_size (минимум 1000). Parent берутся целиком в порядке релевантности, пока сумма помещается, — остальные отбрасываются (первый — всегда); не больше top_k. От него: review_context_max_chars.":
        "Auto ≤ llm_budget − audit_map_size (minimum 1000). Parents are taken whole in order of relevance while the total fits — the rest are dropped (the first one always goes); at most top_k. Depending on it: review_context_max_chars.",
    "Подробнее: пять parent по ≈ 2500 симв. с заголовками — это ≈ 13 000 > 9000: в аудит попадают 3 самых релевантных, 4-й и 5-й отбрасываются и не попадают в «Использованные источники». Набор останавливается на первом непоместившемся, даже если следующий короче. Поэтому поднимать top_k ради аудита бессмысленно, пока не поднят этот лимит: для 5 целых parent нужно ≈ 13 000–13 500. Тот же лимит — у норм на вкладке контроля исправлений.":
        "Details: five parents of ≈ 2500 chars with headings are ≈ 13,000 > 9000: review gets the 3 most relevant, the 4th and 5th are dropped and do not appear in “Sources used”. Collection stops at the first one that does not fit, even if the next is shorter. So raising top_k for review is pointless until this limit is raised: 5 whole parents need ≈ 13,000–13,500. Norms on the verification tab have the same limit.",
    "Сколько разделов новой редакции получает модель на одно замечание.":
        "How many sections of the new revision the model gets per comment.",
    "Ограничены review_context_max_chars.":
        "Capped by review_context_max_chars.",
    "Объём этих разделов на одно замечание.":
        "Volume of these sections per comment.",
    "12000 симв.":
        "12000 chars",
    "Авто ≤ llm_budget − audit_context_max_chars − 1000 (минимум 1000); первый раздел передаётся всегда.":
        "Auto ≤ llm_budget − audit_context_max_chars − 1000 (minimum 1000); the first section is always passed.",
    "Сколько символов раздела уходит в эмбеддинг при подборе разделов.":
        "How many characters of a section go into the embedding when matching sections.",
    "4000 симв.":
        "4000 chars",
    "Авто ≤ вход эмбеддингов − префикс документа (минимум 300).":
        "Auto ≤ embedding input − document prefix (minimum 300).",
    "Прочие константы кода (меняются только в коде mint/): сокращение — от 2 до 12 символов, не меньше 2 заглавных; переписанный уточняющий вопрос — до 300 токенов. Остальные константы указаны там, где действуют: запас и резервы окна — в строках параметров выше и в блоке «Токены и символы», алгоритм поиска (BM25, расширение запроса, дедупликация) — в панели 7.":
        "Other code constants (changed only in the mint/ code): an abbreviation is 2 to 12 characters with at least 2 capitals; a rewritten follow-up question is up to 300 tokens. Other constants are given where they act: the margin and window reserves — in the parameter rows above and in the “Tokens and characters” block, the search algorithm (BM25, query expansion, deduplication) — in panel 7.",
    "4. Особенности компании → на что влияют и как настраивать":
        "4. Features of your organisation → what they affect and how to tune",
    "Что из исходных условий меняет настройки MINT. Пункты с [Т] сравниваются проверкой качества до и после изменения.":
        "Which starting conditions change MINT's settings. Items marked [T] are compared with a quality check before and after the change.",
    "Особенность компании":
        "Feature of the organisation",
    "На что влияет в MINT":
        "What it affects in MINT",
    "Как настраивать":
        "How to tune",
    "Размер базы: сколько документов и фрагментов":
        "Size of the base: how many documents and fragments",
    "НЕ влияет на размеры фрагментов, пороги реранкера, промпты. ВЛИЯЕТ на: авто-top_k (панель 3); глубину кандидатов initial_k / bm25_top_k / rerank_top_k (похожих документов больше — правильный дальше в списке); пороги «уверенность низкая»; память и время (панель 9).":
        "Does NOT affect fragment sizes, reranker thresholds, prompts. DOES affect: auto top_k (panel 3); candidate depth initial_k / bm25_top_k / rerank_top_k (more similar documents — the correct one lower in the list); the “low confidence” thresholds; memory and time (panel 9).",
    "[Т] если правильный фрагмент всё чаще «> 10» — initial_k 80–100, bm25_top_k 30, rerank_top_k 24; перекалибровать low_conf_rerank / low_conf_lexical. [Р] top_k задать явно, если авто-выбор не устраивает.":
        "[T] if the correct fragment is more and more often “> 10” — initial_k 80–100, bm25_top_k 30, rerank_top_k 24; recalibrate low_conf_rerank / low_conf_lexical. [M] set top_k explicitly if the automatic choice does not suit you.",
    "Структура документов: стили заголовков Word":
        "Document structure: Word heading styles",
    "Без стилей «Заголовок 1–3» Docling не находит разделы (collect_structure): в ссылках только имя файла, раздел в контексте и в оценке не виден.":
        "Without the “Heading 1–3” styles Docling finds no sections (collect_structure): references contain only the file name, the section is not visible in the context or in evaluation.",
    "Проставить стили в исходниках и переиндексировать ♻. Нумерованные заголовки обычным стилем MINT пока не распознаёт.":
        "Apply the styles in the source files and re-index ♻. MINT does not yet recognise numbered headings in the normal style.",
    "Длина разделов: короткие пункты регламентов или длинные описания":
        "Section length: short clauses of regulations or long descriptions",
    "parent охватывает несколько коротких пунктов — точные вопросы «тонут» в соседнем тексте; длинным связным описаниям, наоборот, не хватает контекста.":
        "A parent covers several short clauses — precise questions “drown” in the neighbouring text; long coherent descriptions, on the contrary, lack context.",
    "[Т] на копии базы ♻: короткие пункты и точные вопросы — parent_size 1500–2000; длинные описания — 3000–3500 (если окно LLM позволяет: MINT не даст выйти за потолок). Сравнить --compare.":
        "[T] on a copy of the base ♻: short clauses and precise questions — parent_size 1500–2000; long descriptions — 3000–3500 (if the LLM window allows: MINT will not go above the ceiling). Compare with --compare.",
    "Много таблиц: матрицы требований, SLA, перечни":
        "Many tables: requirement matrices, SLAs, lists",
    "Большая таблица делится на части с повтором шапки; часть из них может не попасть в контекст (max_table_parts).":
        "A large table is split into parts with the header repeated; some of them may not get into the context (max_table_parts).",
    "[П] max_table_parts 3–4, если вопросы часто про таблицы; [Т] добавить такие вопросы в набор eval и смотреть hit@K.":
        "[C] max_table_parts 3–4 if questions are often about tables; [T] add such questions to the eval set and watch hit@K.",
    "Много сокращений и внутренних названий систем":
        "Many abbreviations and internal system names",
    "Эмбеддинги не знают внутренних названий — их находят BM25 и глоссарий.":
        "Embeddings do not know internal names — BM25 and the glossary find them.",
    "[Р] glossary.json для сокращений, которых нет в документах (шаг 4, панель 5); [Т] если «только BM25» заметно лучше «только dense» — weight_bm25 1.3–1.5.":
        "[M] glossary.json for abbreviations that are not in the documents (step 4, panel 5); [T] if “BM25 only” is clearly better than “dense only” — weight_bm25 1.3–1.5.",
    "Несколько редакций одного документа в базе":
        "Several revisions of one document in the base",
    "Дубли занимают места в top_k; дедупликация убирает только совпадающие фрагменты; модель может сослаться на устаревшую редакцию.":
        "Duplicates take places in top_k; deduplication removes only identical fragments; the model may cite an outdated revision.",
    "[Р] держать в базе только действующие редакции (старые удалять); в именах файлов — номер редакции; иначе [Т] top_k выше.":
        "[M] keep only current revisions in the base (delete old ones); put the revision number into file names; otherwise [T] a higher top_k.",
    "Как спрашивают пользователи: термины, длинные ситуации, диалог":
        "How users ask: terms, long situations, dialogue",
    "Короткие термины и коды лучше ищет BM25; длинные «своими словами» — вектор; уточнения «а для второго контура?» требуют истории.":
        "Short terms and codes are better found by BM25; long “in my own words” questions — by vector; follow-ups like “and for the second circuit?” need the history.",
    "[Т] веса weight_dense / weight_bm25, use_multi_query для расплывчатых вопросов; [П] chat_history_turns 0 / 2 / 3. Набор вопросов для eval — из реальных обращений.":
        "[T] weights weight_dense / weight_bm25, use_multi_query for vague questions; [C] chat_history_turns 0 / 2 / 3. The eval question set — from real requests.",
    "Язык документов: русский, английский, смешанные":
        "Language of documents: Russian, English, mixed",
    "BM25 приводит слова к основам русским (Snowball) или английским (Porter2) стеммером — по каждому слову; коды ищутся точно; смысловой поиск зависит от модели эмбеддингов.":
        "BM25 reduces words to stems with a Russian (Snowball) or English (Porter2) stemmer — word by word; codes are matched exactly; semantic search depends on the embedding model.",
    "[Р] многоязычная модель эмбеддингов (Qwen3-Embedding, bge-m3, multilingual-e5) ♻ — смена модели требует переиндексации; MINT_LANG — язык интерфейса, промптов и отчётов; «Определить у сервера» — после загрузки документов на другом языке.":
        "[M] a multilingual embedding model (Qwen3-Embedding, bge-m3, multilingual-e5) ♻ — changing the model requires re-indexing; MINT_LANG — language of the interface, prompts and reports; “Detect from server” — after uploading documents in another language.",
    "Требования к ответам: строгость, длина, ссылки":
        "Requirements for answers: strictness, length, references",
    "Строгость — temperature; длина — max_tokens (место под ответ отнимается у контекста, панель 2).":
        "Strictness — temperature; length — max_tokens (room for the answer is taken from the context, panel 2).",
    "[П] temperature 0–0.2; max_tokens — по длине типичного ответа; ссылки [файл, раздел] — в CHAT_SYSTEM_PROMPT / CHAT_SYSTEM_PROMPT_EN; ссылки мимо контекста check_citations() помечает ⚠.":
        "[C] temperature 0–0.2; max_tokens — by the length of a typical answer; [file, section] references — in CHAT_SYSTEM_PROMPT / CHAT_SYSTEM_PROMPT_EN; check_citations() marks references outside the context with ⚠.",
    "Модели компании: окно LLM, входы эмбеддингов и реранкера, рассуждения":
        "Your models: LLM window, embedding and reranker inputs, reasoning",
    "Определяют все [А]-параметры через потолки (панели 1–2); модели с рассуждениями тратят max_tokens и на <think> (strip_reasoning убирает рассуждения из ответа).":
        "They determine all [A] parameters through the ceilings (panels 1–2); reasoning models also spend max_tokens on <think> (strip_reasoning removes the reasoning from the answer).",
    "[П] модели с рассуждениями: max_tokens 3000–4000 (иначе ответ обрывается — «Ответ модели обрезан»), llm_timeout 150–180; новая модель эмбеддингов ♻ — переиндексация (kb_document_status покажет).":
        "[C] reasoning models: max_tokens 3000–4000 (otherwise the answer breaks off — “Answer truncated”), llm_timeout 150–180; a new embedding model ♻ — re-indexing (kb_document_status shows it).",
    "Корпоративный шлюз: лимиты запросов, таймауты, TLS":
        "Corporate gateway: request limits, timeouts, TLS",
    "HTTP 400 от реранкера при больших пачках, 429 / 504 при нагрузке, собственный сертификат.":
        "HTTP 400 from the reranker on large batches, 429 / 504 under load, an own certificate.",
    'Регламент проверки документов: критерии, чек-листы, объём документа':
        'Document review rules: criteria, checklists, document size',
    'Критерии и чек-листы задают, что ищет аудит; размер раздела — детальность и число вызовов LLM.':
        'Criteria and checklists define what review looks for; the section size — the level of detail and the number of LLM calls.',
    "[Р] общие критерии — поле на вкладке «Аудит документа» (по умолчанию DEFAULT_AUDIT_FOCUS), чек-листы по типам документов — checklists.yaml (файл вне папки программы — путь в MINT_CHECKLISTS); пункты, важные для конкретного документа, — в поле «Особое внимание»; [П] audit_map_size и use_self_critique — на живой проверке (шаг 9, панель 5).":
        "[M] general criteria — the field on the “Document review” tab (default DEFAULT_AUDIT_FOCUS / DEFAULT_AUDIT_FOCUS_EN), checklists by document type — checklists.yaml (a file outside the program folder — its path in MINT_CHECKLISTS); points that matter for a particular document — in the “Special attention” field; [C] audit_map_size and use_self_critique — on a live check (step 9, panel 5).",
    "Нагрузка: число одновременных пользователей":
        "Load: number of simultaneous users",
    "Все сеансы делят шлюз LLM; разбор документов и запись в базу идут по очереди (панель 6).":
        "All sessions share the LLM gateway; document parsing and writes to the base run one at a time (panel 6).",
    "[Р] лимиты шлюза и llm_retries; загрузку больших пакетов документов — вне часов пик.":
        "[M] gateway limits and llm_retries; upload large batches of documents outside peak hours.",
    "5. Порядок настройки у себя":
        "5. Setting it up at your place",
    "Шаги 6–8 повторяются: база выросла в 2 раза, новый тип документов, другая модель эмбеддингов или реранкера, изменены parent_size / child_size.":
        "Steps 6–8 are repeated when: the base has doubled, a new type of documents, another embedding model or reranker, parent_size / child_size changed.",
    "1. Подключения .env: адреса, ключи, модели, KB_DIR, сертификат. check_install.py без ошибок; в панели нет красных ошибок, реранкер «доступен» или «не подключён».":
        "1. Connections\n.env: addresses, keys, models, KB_DIR, certificate. check_install.py without errors; no red errors in the sidebar, the reranker is “available” or “not connected”.",
    "2. Лимиты моделей «Модели и лимиты» → «Определить у сервера». Чего сервер не сообщает — в config.yaml (models). Проверить «MINT рассчитал» и предупреждения.":
        "2. Model limits\n“Models and limits” → “Detect from server”. What the server does not report — into config.yaml (models). Check “Computed by MINT” and the warnings.",
    "3. Документы Загрузить. Сообщения загрузки: «Распознано заголовков: N» (0 — нет стилей, панель 4), «Пропущено … чанков» — сбой эмбеддингов.":
        "3. Documents\nUpload. Upload messages: “Headings recognised: N” (0 — no styles, panel 4), “Skipped … chunks” — an embedding failure.",
    "4. Сокращения Список «Сокращения» в панели: неточные расшифровки и недостающие сокращения — в glossary.json.":
        "4. Abbreviations\nThe “Abbreviations” list in the sidebar: inaccurate expansions and missing abbreviations — into glossary.json.",
    "5. Набор вопросов Кнопка «Проверка качества» на боковой панели: MINT составит черновик — переписать своими словами, добавить реальные вопросы и 5–10 без ответа в базе. Всего 40–60.":
        "5. Question set\nThe “Quality check” button in the sidebar: MINT writes a draft — reword it, add real questions and 5–10 without an answer in the base. 40–60 in total.",
    "6. Точка отсчёта «Запустить проверку» → итоги на странице; report.md, details.csv, summary.json — в LOG_DIR/eval (в консоли — eval_search.py questions.csv).":
        "6. Baseline\n“Run the check” → results on the page; report.md, details.csv, summary.json — in LOG_DIR/eval (from the console — eval_search.py questions.csv).",
    "7. Настройка по отчёту «Что поменять» → «Применить в этой сессии»; закрепить в config.yaml: weight_rerank, веса dense / BM25, пороги low_conf, top_k, multi-query.":
        "7. Tuning from the report\n“What to change” → “Apply to this session”; keep it in config.yaml: weight_rerank, dense / BM25 weights, low_conf thresholds, top_k, multi-query.",
    "8. Проверка Следующая проверка сравнивается с прошлой (▲▼; в консоли — --compare): MRR и hit@K выросли, ложные тревоги не выросли; разница не случайна (p < 0.05).":
        "8. Check\nThe next check is compared with the last one (▲▼; from the console — --compare): MRR and hit@K went up, false alarms did not; the difference is not chance (p < 0.05).",
    "9. Живая проверка 15–20 ответов в чате; аудит 3–5 документов с известными замечаниями; контроль — пары редакций. Подстроить [П]-параметры.":
        "9. Live check\n15–20 chat answers; review of 3–5 documents with known findings; verification — pairs of revisions. Adjust the [C] parameters.",
    "Как работает проверка качества — mint/evaluation.py: кнопка «Проверка качества» на боковой панели и eval_search.py в консоли (тот же код поиска, что в чате; база и сервисы — настоящие; LLM — только для черновика вопросов, ответов чата и multi-query) generate_questions(): по фрагменту — вопрос на языке фрагмента и дословная цитата → таблица вопросов: правка, свои вопросы; rows_to_questions() и markup_problems() — разметка, которая никогда не засчитается → request_cache() (каждый запрос к сервисам — один раз на все варианты) → build_configs(): только dense, только BM25, гибрид, гибрид + реранкер 0.35 / 0.7 / 1 / 1.5 / 3 → run_question(): search_parent_child() на глубину 10 + diagnostics при top_k → is_relevant(): файл + раздел (в пути или заголовком внутри фрагмента) + фраза → metrics(): hit@1, hit@3, hit@K, MRR, ложные тревоги → paired() + sign_test_p(): на скольких вопросах конфигурации расходятся и случайна ли разница (критерий знаков) → calibrate(): порог по тому же правилу, что в поиске (is_low_confidence) → check_answers() по желанию (1–3 раза): ответ чата (answer_question), ссылка на нужный документ, ссылки мимо найденного, ложное и честное «информации нет» (chat_no_info), ошибка поиска или модели; compare_answers() — с прошлой проверкой ответов по вопросам и версии промптов → recommendations(): что поменять → save_run(): report.md, details.csv без пустых ячеек, summary.json, questions.csv — в LOG_DIR/eval.":
        "How the quality check works — mint/evaluation.py: the “Quality check” button in the sidebar and eval_search.py from the console (the same search code as in chat; the base and services are real; the LLM only writes the draft questions, chat answers and multi-query)\ngenerate_questions(): per fragment — a question in the fragment's language and a verbatim quote → the question table: edits, your own questions; rows_to_questions() and markup_problems() — labels that can never be counted → request_cache() (each service request once for all variants) → build_configs(): dense only, BM25 only, hybrid, hybrid + reranker 0.35 / 0.7 / 1 / 1.5 / 3 → run_question(): search_parent_child() to depth 10 + diagnostics at top_k → is_relevant(): file + section (in the path or as a heading inside the fragment) + phrase → metrics(): hit@1, hit@3, hit@K, MRR, false alarms → paired() + sign_test_p(): on how many questions configurations differ and whether the difference is chance (sign test) → calibrate(): the threshold by the same rule as in search (is_low_confidence) → check_answers() optionally (1–3 times): the chat answer (answer_question), a reference to the right document, references outside the fragments found, false and honest “no information” (chat_no_info), a search or a model error; compare_answers() — with the previous answer check, question by question and by prompt version → recommendations(): what to change → save_run(): report.md, details.csv without empty cells, summary.json, questions.csv — in LOG_DIR/eval.",
    "6. Устройство: добавление документов в базу":
        "6. Internals: adding documents to the base",
    "Боковая панель «Добавить документы в базу» → process_and_add_to_kb() для каждого файла. Эмбеддинги считаются без блокировки базы, слияние и запись — под kb_write_lock().":
        "The sidebar's document upload → process_and_add_to_kb() for each file. Embeddings are computed without locking the base; merging and writing — under kb_write_lock().",
    "parse_document() по расширению: .docx — docling_convert() (один DocumentConverter на процесс, по очереди); .pdf — parse_pdf() без моделей; .md, .txt — parse_markdown(), parse_plain_text().":
        "parse_document()\nby extension: .docx — docling_convert() (one DocumentConverter per process, one at a time); .pdf — parse_pdf() without models; .md, .txt — parse_markdown(), parse_plain_text().",
    "collect_structure() обход iterate_items(): section_header / title → стек заголовков, heading_path_str(); table → markdown и подпись; колонтитулы и рисунки пропускаются. Сбой → collect_structure_flat() без заголовков.":
        "collect_structure()\nwalks iterate_items(): section_header / title → heading stack, heading_path_str(); table → markdown and caption; headers, footers and pictures are skipped. On failure → collect_structure_flat() without headings.",
    "build_parent_chunks() текст одним потоком с «## заголовками» → split_with_overlap_pos(parent_size ♻, parent_overlap ♻; разрез по абзацу, строке, предложению, слову; заголовок — со своим текстом) → в каждом parent child (child_size ♻, child_overlap ♻); путь заголовков child — по его позиции (bisect). Таблицы: clean_table_markdown() → split_table_markdown() по строкам с повтором шапки.":
        "build_parent_chunks()\ntext as one stream with “## headings” → split_with_overlap_pos(parent_size ♻, parent_overlap ♻; cuts at a paragraph, line, sentence, word; a heading stays with its text) → children in each parent (child_size ♻, child_overlap ♻); a child's heading path — by its position (bisect). Tables: clean_table_markdown() → split_table_markdown() by rows with the header repeated.",
    "index_parsed_document() вход эмбеддинга = embed_doc_prefix ♻ + путь заголовков + child → get_query_embeddings_batch() (пачками по embed_batch_size; _embed_input() обрезает до embed_input_max_chars) → l2_normalize().":
        "index_parsed_document()\nembedding input = embed_doc_prefix ♻ + heading path + child → get_query_embeddings_batch() (in batches of embed_batch_size; _embed_input() cuts to embed_input_max_chars) → l2_normalize().",
    "Запись под kb_write_lock() перечитать базу, убрать прежнюю версию файла, проверить размерность векторов → IndexFlatL2 → _commit_kb(): временная папка + os.replace → save_bm25_index() → rebuild_auto_glossary() (extract_abbreviations → build_auto_glossary).":
        "Write under kb_write_lock()\nre-read the base, remove the previous version of the file, check the vector dimension → IndexFlatL2 → _commit_kb(): temporary folder + os.replace → save_bm25_index() → rebuild_auto_glossary() (extract_abbreviations → build_auto_glossary).",
    "child_index.faiss векторы child, нормированы (поиск по косинусу)":
        "child_index.faiss\nchild vectors, normalised (cosine search)",
    "parent_store.json текст parent, heading_path, type, section, page":
        "parent_store.json\nparent text, heading_path, type, section, page",
    "bm25_index.pkl основы слов, позиции; подпись формата (иначе пересборка)":
        "bm25_index.pkl\nword stems, positions; format signature (otherwise rebuilt)",
    "auto_glossary.json сокращения из документов":
        "auto_glossary.json\nabbreviations from documents",
    "manifest.json embed_model, embed_dim, префикс, parent / child для каждого документа":
        "manifest.json\nembed_model, embed_dim, prefix, parent / child for each document",
    "sources/ оригиналы документов для переиндексации":
        "sources/\noriginal documents for re-indexing",
    "Хранилище — папка KB_DIR":
        "Store — the KB_DIR folder",
    "Обслуживание и чтение базы • kb_document_status(): сравнивает manifest с текущими настройками — «другая модель эмбеддингов» (векторный поиск по документу не работает) или «другая нарезка / загружен до v18». • reindex_documents(): по sources/; если сменилась размерность векторов — _clear_kb_index() и сборка заново. delete_document_from_kb() — удаление с оригиналом. • load_kb_snapshot(): кэш по времени изменения файлов, короткая блокировка на чтение; normalized_index() нормирует старую базу в памяти. load_bm25_for(): пересборка при смене формата или набора фрагментов. load_glossary(): glossary.json важнее автоглоссария, старый формат v17 понимается.":
        "Maintaining and reading the base\n• kb_document_status(): compares the manifest with the current settings — “another embedding model” (vector search over the document does not work) or “other chunking / uploaded before v18”.\n• reindex_documents(): from sources/; if the vector dimension changed — _clear_kb_index() and a full rebuild. delete_document_from_kb() — removal together with the original.\n• load_kb_snapshot(): cache by file modification time, a short read lock; normalized_index() normalises an old base in memory. load_bm25_for(): rebuild when the format or the set of fragments changes. load_glossary(): glossary.json wins over the auto-glossary, the old v17 format is understood.",
    "7. Устройство: поиск search_parent_child() и ответ в чате":
        "7. Internals: search_parent_child() and the chat answer",
    "Шаги общие для чата, аудита (build_norms_context) и контроля исправлений; ответ LLM — только в чате. Параметры названы по имени — значения и категории в справочнике (панель 3).":
        "The steps are shared by chat, review (build_norms_context) and verification of fixes; the LLM answer — only in chat. Parameters are named — values and categories are in the reference (panel 3).",
    "chat_history() + condense_question() только в чате: последние chat_history_turns пар «вопрос — ответ»; уточнение → самостоятельный вопрос (CONDENSE_SYSTEM).":
        "chat_history() + condense_question()\nchat only: the last chat_history_turns “question — answer” pairs; a follow-up → a self-contained question (CONDENSE_SYSTEM).",
    "analyze_query() вопросы «что такое X», «состав X», «what is X», «components of X» (до 300 симв.): предмет X → буст точной фразы; слова расширения ×0.3, слова предмета +0.5 — только в BM25. expand_query_multi() — если use_multi_query.":
        "analyze_query()\nquestions “what is X”, “components of X” and their Russian forms (up to 300 chars): subject X → exact-phrase boost; expansion words ×0.3, subject words +0.5 — in BM25 only. expand_query_multi() — if use_multi_query.",
    "Вектор: _query_vector() embed_query_prefix + вопрос → эмбеддинг → l2_normalize() → FAISS search: initial_k child → их parent; best_child — текст для реранкера. Нет эмбеддинга или другая размерность — канал выключается, работает BM25.":
        "Vector: _query_vector()\nembed_query_prefix + question → embedding → l2_normalize() → FAISS search: initial_k children → their parents; best_child — the text for the reranker. No embedding or another dimension — the channel is off, BM25 works.",
    "Слова: LightweightBM25.get_scores() основы слов (russian_stem — кириллица от 5 букв, english_stem — латиница от 4 букв), без стоп- и вопросительных слов (RU и EN); + Glossary.bm25_terms() ×0.5; k1 1.5, b 0.75, IDF ≥ 0.25; точная фраза +10 (до 8 слов); соседние слова вопроса рядом (≤ 3, до 12 значимых слов) +2 → bm25_top_k.":
        "Words: LightweightBM25.get_scores()\nword stems (russian_stem — Cyrillic words from 5 letters, english_stem — Latin words from 4 letters), without stop and question words (EN and RU); + Glossary.bm25_terms() ×0.5; k1 1.5, b 0.75, IDF ≥ 0.25; exact phrase +10 (up to 8 words); question words close together (≤ 3, up to 12 significant words) +2 → bm25_top_k.",
    "Слияние RRF вклад списка = вес / (rrf_constant + место): weight_dense, weight_bm25 → rerank_top_k кандидатов.":
        "RRF fusion\ncontribution of a list = weight / (rrf_constant + place): weight_dense, weight_bm25 → rerank_top_k candidates.",
    "Реранкер (если задан RERANK_API_URL) Glossary.enrich_query(); rerank_document(): имя файла и раздел + child с окружением (passage_around) или окно с наибольшей плотностью слов (best_window), до rerank_doc_max_chars → rerank_scores(): все кандидаты пачками (rerank_max_docs, rerank_char_budget); сбой части пачек — баллы не учитываются. Голос: балл ≥ min_rerank_score → + weight_rerank / (rrf_constant + место).":
        "Reranker (if RERANK_API_URL is set)\nGlossary.enrich_query(); rerank_document(): file name and section + the child with its surroundings (passage_around) or the window densest in question words (best_window), up to rerank_doc_max_chars → rerank_scores(): all candidates in batches (rerank_max_docs, rerank_char_budget); if some batches fail, no scores are used. Vote: score ≥ min_rerank_score → + weight_rerank / (rrf_constant + place).",
    "Контекст merge_adjacent(): соседние фрагменты одного документа — один блок в порядке текста; _source_header(): файл | раздел в начале фрагмента | далее во фрагменте (inner_headings, до 8) | таблица | стр.; focus_passage(): длиннее smart_truncate_chars — вокруг найденного места. В списке источников — раздел, где найдено место (section_at).":
        "Context\nmerge_adjacent(): neighbouring fragments of one document — one block in text order; _source_header(): file | section at the start of the fragment | further in the fragment (inner_headings, up to 8) | table | page; focus_passage(): longer than smart_truncate_chars — around the match. The source list shows the section where the match is (section_at).",
    "Сигнал «уверенность низкая» is_low_confidence(): с реранкером — его лучший балл < low_conf_rerank; без реранкера — доля слов вопроса в контексте < low_conf_lexical и dense с BM25 не совпали в топ-low_conf_agree_top → LOW_CONFIDENCE_NOTE в начале контекста.":
        "The “low confidence” signal\nis_low_confidence(): with a reranker — its best score < low_conf_rerank; without one — share of question words in the context < low_conf_lexical and dense and BM25 did not agree in the top low_conf_agree_top → LOW_CONFIDENCE_NOTE at the start of the context.",
    "Ответ (чат) Glossary.reference_block() до glossary_max_entries; chat_user_content(); ask_llm(chat_system_prompt() — RU / EN, история): temperature, max_tokens; strip_reasoning() убирает <think>; finish_reason = length → пометка «ответ обрезан»; check_citations(): ссылки [файл, раздел] сверяются с контекстом, неверные — ⚠ и предупреждение под ответом.":
        "Answer (chat)\nGlossary.reference_block() up to glossary_max_entries; chat_user_content(); ask_llm(chat_system_prompt() — EN / RU, history): temperature, max_tokens; strip_reasoning() removes <think>; finish_reason = length → “answer truncated” mark; check_citations(): [file, section] references are checked against the context, wrong ones — ⚠ and a warning under the answer.",
    "Отбор top_k без повторов (файл + первые 80 симв.); не больше max_table_parts частей одной таблицы.":
        "Select top_k\nno duplicates (file + first 80 chars); at most max_table_parts parts of one table.",
    "Реранкер с пунктирной рамкой — необязательный: без него порядок задают шаги «Вектор», «Слова» и «Слияние RRF». Нормализация слов (normalize_token: russian_stem / english_stem) общая для индекса BM25, запроса и глоссария.":
        "The reranker with a dashed frame is optional: without it the order is set by the “Vector”, “Words” and “RRF fusion” steps. Word normalisation (normalize_token: russian_stem / english_stem) is shared by the BM25 index, the query and the glossary.",
    "8. Устройство: аудит документа, контроль исправлений и черновик карточки системы":
        "8. Internals: document review, verification of fixes and the system card draft",
    "Вкладки «Аудит документа» и «Контроль исправлений», кнопка черновика карточки на боковой панели. Сколько вызовов сервисов уходит на раздел, замечание и карточку — панель 9.":
        "The “Document review” and “Verification of fixes” tabs, the card draft button on the sidebar. How many service calls go into a section, a comment and a card — panel 9.",
    "АУДИТ ДОКУМЕНТА — вкладка «Аудит документа», настройки — блок «⚙️ Настройки аудита» на ней":
        "DOCUMENT REVIEW — the “Document review” tab, settings — the “⚙️ Review settings” block on it",
    "Нормы «особое внимание» → special_focus_norms(): один поиск на аудит, до 2 parent (низкая уверенность — нет). Для раздела build_norms_context(): smart_truncate(раздел, audit_query_chars) → search_parent_child() → сначала нормы по особому вниманию, затем раздела; целые parent до audit_context_max_chars; нет — NO_NORMS_NOTE. select_pinned(): правила экспертов и карточки — до audit_pinned_max_chars. basis_references() → find_basis_documents(): документы-основания по шифру и названию — их ближайшие к разделу фрагменты до audit_basis_max_chars.":
        "Norms\n“special attention” → special_focus_norms(): one search per review, up to 2 parents (low confidence — none). For a section build_norms_context(): smart_truncate(section, audit_query_chars) → search_parent_child() → norms for special attention first, then for the section; whole parents up to audit_context_max_chars; none — NO_NORMS_NOTE. select_pinned(): expert rules and cards — up to audit_pinned_max_chars. basis_references() → find_basis_documents(): basis documents by code and title — their fragments closest to the section up to audit_basis_max_chars.",
    "Документ с замечаниями annotate_docx_with_findings(): _locate_by_quote() → _isolate_range() → add_comment(); без цитаты — _locate_by_words() (≥ 2 слов и ≥ 30 %, однозначно); иначе — список в начале документа.":
        "Document with findings\nannotate_docx_with_findings(): _locate_by_quote() → _isolate_range() → add_comment(); without a quote — _locate_by_words() (≥ 2 words and ≥ 30 %, unambiguous); otherwise — a list at the start of the document.",
    "КОНТРОЛЬ ИСПРАВЛЕНИЙ — вкладка «Контроль исправлений»":
        "VERIFICATION OF FIXES — the “Verification of fixes” tab",
    "document_to_markdown() → split_into_sections() новая редакция документа, разделы до audit_map_size.":
        "document_to_markdown() → split_into_sections()\nthe new revision of the document, sections up to audit_map_size.",
    "build_section_index() эмбеддинги разделов (до section_embed_chars) + LightweightBM25 по разделам; один раз на документ.":
        "build_section_index()\nsection embeddings (up to section_embed_chars) + LightweightBM25 over sections; once per document.",
    "verify_remark(): подбор нормы — build_norms_context() (галочка «база знаний»); pick_sections_for_remark(): косинус + BM25 + реранкер (best_window), RRF → review_top_sections разделов до review_context_max_chars.":
        "verify_remark(): matching\nnorms — build_norms_context() (the “knowledge base” checkbox); pick_sections_for_remark(): cosine + BM25 + reranker (best_window), RRF → review_top_sections sections up to review_context_max_chars.",
    "parse_verification() «исправлено» и «частично» засчитываются, только если quote_in_text() нашла цитату в разделах; иначе «не удалось проверить».":
        "parse_verification()\n“fixed” and “partially” count only if quote_in_text() found the quote in the sections; otherwise “could not be verified”.",
    "build_matrix_markdown() / generate_word_matrix() матрица контроля .md и .docx.":
        "build_matrix_markdown() / generate_word_matrix()\nverification matrix .md and .docx.",
    "Ошибки сервисов не превращаются в «чисто»: is_llm_error() — раздел попадает в «не удалось проверить», заключение помечается «проверено не полностью». Заключение и лог разделов хранятся в сеансе и не пропадают после скачивания.":
        "Service errors do not turn into “clean”: is_llm_error() — the section goes to “could not be reviewed”, the report is marked “review incomplete”. The report and the section log are kept in the session and survive downloads.",
    "9. Обращения к сервисам и нагрузка":
        "9. Service calls and load",
    "Для оценки мощностей шлюза под своё число пользователей и объём документов. Все сервисы — OpenAI-совместимый HTTP API.":
        "For sizing the gateway for your number of users and document volume. All services are an OpenAI-compatible HTTP API.",
    "LLM — POST {LLM_API_URL}/chat/completions • ask_llm(): ответ в чате, condense_question(); в аудите — MAP, critique_findings(), глубокая проверка, пункты, merge_duplicate_findings(), select_summary(), compare_with_reference(); verify_remark() в контроле; draft_system_card() — вызов на раздел карточки; --generate в eval • expand_query_multi() — если use_multi_query • _llm_prompt_tokens() — измерение «символов на токен» (max_tokens = 1) • GET {LLM_API_URL}/models — detect_server_info(): список моделей и окна (панель 1) Повторы — llm_retries (панель 3); HTTP 429 — общая пауза всех потоков (_note_rate_limit(), Retry-After), _wait_rate_limit() перед каждым запросом.":
        "LLM — POST {LLM_API_URL}/chat/completions\n• ask_llm(): chat answer, condense_question(); in review — MAP, critique_findings(), the deep review, items, merge_duplicate_findings(), select_summary(), compare_with_reference(); verify_remark() in verification; draft_system_card() — a call per card section; --generate in eval\n• expand_query_multi() — if use_multi_query\n• _llm_prompt_tokens() — measuring “characters per token” (max_tokens = 1)\n• GET {LLM_API_URL}/models — detect_server_info(): model list and windows (panel 1)\nRetries — llm_retries (panel 3); HTTP 429 — a shared pause for all threads (_note_rate_limit(), Retry-After), _wait_rate_limit() before every request.",
    "Эмбеддинги — POST {EMBED_API_URL} • get_query_embedding(): вопрос, раздел документа в аудите, замечание в контроле • get_query_embeddings_batch(): индексация (пачками по embed_batch_size) и build_section_index() • в поиске до 3 попыток с паузой 2 с • GET …/models рядом с EMBED_API_URL — вход модели (панель 1)":
        "Embeddings — POST {EMBED_API_URL}\n• get_query_embedding(): the question, a document section in review, a comment in verification\n• get_query_embeddings_batch(): indexing (in batches of embed_batch_size) and build_section_index()\n• in search up to 3 attempts with a 2 s pause\n• GET …/models next to EMBED_API_URL — the model input (panel 1)",
    "Реранкер — POST {RERANK_API_URL} (необязательно) • _rerank_request() через rerank_scores(): поиск и pick_sections_for_remark() • пачками (rerank_max_docs, rerank_char_budget) • повторов нет: ошибка → поиск без реранкера (в логе — HTTP-код и размер пачки) • probe_reranker() — проверка связи в панели (кэш 5 мин) Ответ: {results: [{index, relevance_score}]} или [{index, score}].":
        "Reranker — POST {RERANK_API_URL} (optional)\n• _rerank_request() via rerank_scores(): search and pick_sections_for_remark()\n• in batches (rerank_max_docs, rerank_char_budget)\n• no retries: an error → search without the reranker (the log shows the HTTP code and the batch size)\n• probe_reranker() — connection check in the sidebar (cached for 5 min)\nResponse: {results: [{index, relevance_score}]} or [{index, score}].",
    "Операция":
        "Operation",
    "Эмбеддинги":
        "Embeddings",
    "Реранкер":
        "Reranker",
    "Что растёт с бизнес-объёмом":
        "What grows with business volume",
    "Вопрос в чате":
        "Chat question",
    "1 (+1 уточнение при истории, +1 multi-query)":
        "1 (+1 rewrite with history, +1 multi-query)",
    "≈ 2 запроса (16 кандидатов пачками)":
        "≈ 2 requests (16 candidates in batches)",
    "число пользователей × вопросов в день":
        "number of users × questions per day",
    "Аудит документа, на раздел":
        "Document review, per section",
    "Контроль исправлений, на замечание":
        "Verification of fixes, per comment",
    "1 (+1 с нормами)":
        "1 (+1 with norms)",
    "≈ 1–2 (+2 с нормами)":
        "≈ 1–2 (+2 with norms)",
    "число замечаний; плюс эмбеддинги всех разделов новой редакции один раз":
        "number of comments; plus embeddings of all sections of the new revision once",
    "Загрузка документа":
        "Document upload",
    "child / embed_batch_size запросов":
        "child / embed_batch_size requests",
    "≈ 1 child на 250 симв. (400 − перекрытие 150): 250 тыс. симв. ≈ 1000 child ≈ 32 запроса":
        "≈ 1 child per 250 chars (400 − overlap 150): 250,000 chars ≈ 1000 children ≈ 32 requests",
    "Проверка качества (и eval_search.py)":
        "Quality check (and eval_search.py)",
    "1 на вопрос при составлении вопросов; +1 с ответами чата или multi-query":
        "1 per question when writing questions; +1 with chat answers or multi-query",
    "1 на вопрос":
        "1 per question",
    "≈ 2 на вопрос":
        "≈ 2 per question",
    "ответы кэшируются на все варианты настроек":
        "answers are cached for all setting variants",
    "Память и диск (один процесс Streamlit на всех пользователей): FAISS IndexFlatL2 в памяти — child × размерность × 4 байта (Qwen3-Embedding-4B, 2560: ≈ 10 КБ на child, 10 000 child ≈ 100 МБ); BM25 — позиции слов всех parent; кэш _process_cache() держит базу одним экземпляром. Диск KB_DIR: индексы + оригиналы sources/. LOG_DIR: mint_system.log (до 60 МБ с ротацией) и feedback.jsonl — растёт с числом отзывов.":
        "Memory and disk (one Streamlit process for all users): FAISS IndexFlatL2 in memory — children × dimension × 4 bytes (Qwen3-Embedding-4B, 2560: ≈ 10 KB per child, 10,000 children ≈ 100 MB); BM25 — word positions of all parents; the _process_cache() cache keeps one copy of the base. Disk KB_DIR: indexes + the sources/ originals. LOG_DIR: mint_system.log (up to 60 MB with rotation) and feedback.jsonl — grows with the number of feedback entries.",
    "document_to_markdown() .docx — Docling → export_to_markdown() → clean_docling_markdown() (повторы объединённых ячеек) → compact_markdown_tables() (без выравнивания); .pdf — parse_pdf() → blocks_to_markdown().":
        "document_to_markdown()\n.docx — Docling → export_to_markdown() → clean_docling_markdown() (duplicates of merged cells) → compact_markdown_tables() (no padding); .pdf — parse_pdf() → blocks_to_markdown().",
    "Разделы split_minor_findings(): главное, мелкие, опечатки → group_by_section(): по разделам документа, в его порядке; corroboration() — сколько проверок нашли замечание.":
        "Sections\nsplit_minor_findings(): main, minor, typos → group_by_section(): by document section, in document order; corroboration() — how many checks found the finding.",
    "1 (+1 на аудит и +1 на пункт при «особом внимании»)":
        "1 (+1 per review and +1 per point with “special attention”)",
    "MAP audit_section(): документ целиком или оглавление + location_line() + часть → ask_llm() → parse_findings() (подпункты — к своему замечанию) → finding_from_line(); с оглавлением — verify_absence(). Разделы — параллельно (audit_parallel).":
        "MAP\naudit_section(): the whole document or the outline + location_line() + the part → ask_llm() → parse_findings() (sub-items stay in their finding) → finding_from_line(); with the outline — verify_absence(). Sections — in parallel (audit_parallel).",
    "Самокритика use_self_critique: critique_findings() — CRITIQUE_SYSTEM, документ целиком + «особое внимание» (такие замечания удаляются только при опровержении) → JSON {verdict, severity, category, quote}; цитата сверяется quote_in_text().":
        "Self-critique\nuse_self_critique: critique_findings() — CRITIQUE_SYSTEM, the whole document + “special attention” (such findings are dropped only when refuted) → JSON {verdict, severity, category, quote}; the quote is checked by quote_in_text().",
    "split_document_parts() по разделам: заголовок с текстом и таблицами; мелкие — вместе до audit_map_size, раздел до 1,5 лимита — целым; большая таблица — по строкам с шапкой. document_mode(): документ целиком, если помещается в окно, иначе document_outline(). «Весь документ одним запросом» — whole_document_part().":
        "split_document_parts()\nby section: a heading with its text and tables; small ones together up to audit_map_size, a section up to 1.5 limits — whole; a large table — by rows with the header. document_mode(): the whole document if it fits into the window, otherwise document_outline(). “The whole document in one request” — whole_document_part().",
    "Подробнее: Документ режется на части по разделам до этого размера (раздел до 1,5 размера — целым), каждая проверяется отдельным вызовом LLM. Чтобы модель не писала «не указано X», когда X есть в другом разделе, к части прилагается документ целиком (audit_full_document) или оглавление.":
        "Details: The document is split into parts by section up to this size (a section up to 1.5 sizes stays whole), each checked by a separate LLM call. So that the model does not write “X is not specified” when X is in another section, the part comes with the whole document (audit_full_document) or the outline.",
    "Документ целиком в каждой проверке раздела и самокритике.":
        "The whole document in every section review and self-critique.",
    "Только если документ помещается в окно модели; иначе — оглавление и сверка «не описано» с другими разделами.":
        "Only if the document fits into the model's window; otherwise the outline and checking “not described” against other sections.",
    "Сведение повторов замечаний моделью в конце аудита.":
        "Merging duplicate findings with the model at the end of the review.",
    "+1 вызов LLM; выключено — повторы склеиваются только по совпадению слов.":
        "+1 LLM call; when off, duplicates are merged only when their words match.",
    "Общеизвестные сокращения, которые проверка сокращений не отмечает.":
        "Well-known abbreviations the abbreviation check does not flag.",
    "Через запятую; ГОСТ, РФ, API и подобные уже учтены.":
        "Comma-separated; GOST, RF, API and the like are already included.",
    "0 — без лимита; первыми — процесс и цифры.":
        "0 — no limit; the process and figures first.",
    "Десятки коротких вызовов LLM; модель среднего размера справляется с узким вопросом надёжнее, чем с аудитом главы.":
        "Dozens of short LLM calls; a medium-sized model handles a narrow question more reliably than a review of a whole section.",
    "частей ≈ объём документа / audit_map_size: ФТ на 20 тыс. симв. ≈ 6 частей ≈ 12 вызовов LLM + ≈ 35 коротких вопросов глубокой проверки (шагов процесса, требований и частей); документ целиком добавляет свой объём во вход каждой проверки раздела":
        "parts ≈ document size / audit_map_size: 20,000-char requirements ≈ 6 parts ≈ 12 LLM calls + ≈ 35 short deep review questions (process steps, requirements and parts); the whole document adds its size to the input of every section review",
    "2 (MAP + самокритика) или 1; на аудит: +1 на пункт «особого внимания» и чек-листа, +1 на систему с карточкой, +1 сведение повторов, +1 «Главное», с оглавлением — сверка «не описано» (до 15); глубокая проверка — до audit_deep_max_calls; проходы 2–3 (audit_passes) повторяют разделы и вопросы о процессе и цифрах":
        "2 (MAP + self-critique) or 1; per review: +1 per “special attention” and checklist item, +1 per system with a card, +1 merging duplicates, +1 “Key points”, with the outline — checking “not described” (up to 15); the deep review — up to audit_deep_max_calls; passes 2–3 (audit_passes) repeat the sections and the process and figures questions",
    "Проходов проверки разделов и вопросов глубокой проверки о процессе и цифрах.":
        "Passes of the section review and of the deep review questions about the process and figures.",
    "2–3 — с температурой ≥ 0,4; замечания проходов сводятся, найденное несколько раз — выше.":
        "2–3 — with temperature ≥ 0.4; the findings of the passes are merged, what is found several times ranks higher.",
    "«Главное» в начале заключения: самые важные замечания указателями на номера.":
        "“Key points” at the top of the report: the most important findings as pointers to their numbers.",
    "+1 вызов LLM (модель-редактор); 0 — без блока.":
        "+1 LLM call (editor model); 0 — no block.",
    "Аудит с рассуждениями модели (поверх llm_no_reasoning).":
        "Review with model reasoning (overrides llm_no_reasoning).",
    "Ответ +6000 токенов на рассуждения, таймаут ≥ 300 с; в чате рассуждения как настроено.":
        "Answer +6000 tokens for reasoning, timeout ≥ 300 s; in the chat reasoning stays as configured.",
    "Не больше стольких вопросов глубокой проверки.":
        "At most this many deep review questions.",
    "Больше — быстрее; при ответах 429 и таймаутах — уменьшить.":
        "More is faster; reduce it on 429 answers and timeouts.",
    "Глубокая проверка: узкие вопросы модели по процессу, противоречиям, цифрам, опечаткам.":
        "Deep review: narrow questions to the model on the process, contradictions, figures, typos.",
    "Запросов аудита одновременно: разделы, вопросы глубокой проверки, пункты.":
        "Review requests at the same time: sections, deep review questions, items.",
    "Правила экспертов и карточки систем на один запрос аудита (сверх норм).":
        "Expert rules and system cards per review request (on top of the norms).",
    "Помещаются — целиком, иначе — ближайшие к тексту фрагменты; 0 — не передавать.":
        "If they fit — in full, otherwise the fragments closest to the text; 0 — do not pass them.",
    "Что документ требует от каждой упомянутой системы — по её карточке.":
        "What the document requires from each mentioned system — by its card.",
    "+1 вызов LLM на систему, упомянутую в документе не меньше двух раз (до 5 систем).":
        "+1 LLM call per system mentioned in the document at least twice (up to 5 systems).",
    "20000 симв.":
        "20,000 chars",
    "draft_system_card() разделы карточки CARD_SECTIONS (10: названия, назначение, сервисы, лимиты, защита и хранение данных, планы, ограничения, подключение, требования) — параллельно, не больше CARD_PARALLEL и audit_parallel.":
        "draft_system_card()\nthe card sections CARD_SECTIONS (10: names, purpose, services, limits, data protection and storage, plans, limitations, connection, requirements) — in parallel, at most CARD_PARALLEL and audit_parallel.",
    "ask_section() свой запрос к поиску на раздел → search_parent_child(): CARD_TOP_K фрагментов, без multi-query; ничего не найдено — раздел пустой, без вызова LLM.":
        "ask_section()\nits own search query per section → search_parent_child(): CARD_TOP_K fragments, without multi-query; nothing found — the section is empty, no LLM call.",
    "Проходы 2–3 _run_passes() (audit_passes): разделы и вопросы PASS_DEEP_KINDS ещё раз с температурой ≥ PASS_TEMPERATURE (0,4); в origins — «#p2», «#p3»: найденное несколькими проходами считается подтверждённым.":
        "Passes 2–3\n_run_passes() (audit_passes): the sections and the PASS_DEEP_KINDS questions once more at temperature ≥ PASS_TEMPERATURE (0.4); origins get “#p2”, “#p3”: what several passes found counts as corroborated.",
    "Пункты found_so_far_block(): замечания других проверок (до 12 000 симв.) → answer_focus_point(): «особое внимание» и чек-лист — ответ по документу, новые замечания, «из документа не ясно»; answer_system(): что документ требует от системы с карточкой (audit_systems).":
        "Items\nfound_so_far_block(): findings of the other checks (up to 12 000 chars) → answer_focus_point(): “special attention” and the checklist — an answer from the document, new findings, “unclear from the document”; answer_system(): what the document requires from a system with a card (audit_systems).",
    "[Р] черновик карточки по базе — кнопка «Собрать черновик карточки системы по базе» (draft_system_card): эксперт проверяет, дописывает пробелы и загружает в базу с отметкой «Карточки систем»; [П] audit_pinned_max_chars, если карточек много.":
        "[M] a card draft from the base — the “Draft a system card from the base” button (draft_system_card): the expert checks it, fills the gaps and loads it into the base marked “System cards”; [C] audit_pinned_max_chars if there are many cards.",
    "card_markdown() карточка по шаблону: «Названия:» (по ним аудит узнаёт систему в документе), пометка «черновик», разделы CARD_LAYOUT, пробелы «нет в базе», источники — source_name() без баллов поиска → скачать .md.":
        "card_markdown()\nthe card from the template: “Names:” (the review recognizes the system in a document by them), a “draft” mark, the CARD_LAYOUT sections, gaps “not in the base”, sources — source_name() without search scores → download .md.",
    "до 10 (раздел, по которому в базе ничего не нашлось, — без вызова)":
        "up to 10 (a section with nothing found in the base — no call)",
    "до 10 (поиск на раздел)":
        "up to 10 (a search per section)",
    "Справка о системах: что умеют, планы, ограничения":
        "System reference: what they can do, plans, limitations",
    "Глубокая проверка _run_deep(): find_processes() — шаги из таблицы операций, списка шагов или подразделов «Шаг N» → build_deep_tasks() → limit_tasks(): не больше audit_deep_max_calls → run_tasks(): пары шагов, требования, границы, утверждения частей → conflict_tasks(): противоречия; цифры — quantity_calculations(); опечатки.":
        "Deep review\n_run_deep(): find_processes() — steps from a table of operations, a list of steps or “Step N” subsections → build_deep_tasks() → limit_tasks(): at most audit_deep_max_calls → run_tasks(): pairs of steps, requirements, boundaries, claims of parts → conflict_tasks(): contradictions; figures — quantity_calculations(); typos.",
    "Эксперт проверяет факты по источникам, дописывает пробелы (ограничения, планы со сроками), убирает пометку → загружает карточку в базу → отмечает в «Карточки систем»: аудит берёт её в каждую проверку.":
        "Expert\nchecks the facts against the sources, fills the gaps (limitations, plans with dates), removes the mark → loads the card into the base → marks it in “System cards”: the review takes it into every check.",
    "Повтор и проверки без модели _recheck(): разделы, где модель не ответила, — ещё раз с retry_timeout(). check_abbreviations(), check_formatting() — ещё до проверки разделов; unverified_refs() и check_citations(): ссылки и цифры замечаний — в документе и нормах.":
        "Retry and checks without the model\n_recheck(): sections the model did not answer — once more with retry_timeout(). check_abbreviations(), check_formatting() — before the section checks; unverified_refs() and check_citations(): references and figures of findings — in the document and the norms.",
    "ask_llm() card_section_system: только по фрагментам, у каждого факта — [Источник: файл, раздел]; сведений нет — «НЕТ В БАЗЕ».":
        "ask_llm()\ncard_section_system: only from the fragments, every fact with [Source: file, section]; no information — “NOT IN THE BASE”.",
    "Заключение и лог build_final_report(): «Главное», замечания по разделам, ответы на пункты, системы; audit_log_markdown(): лог с настройками прогона; raw_answers_markdown(): сырые ответы модели .md.":
        "Report and log\nbuild_final_report(): “Key points”, findings by section, answers to items, systems; audit_log_markdown(): the log with the run settings; raw_answers_markdown(): raw model answers .md.",
    "ЧЕРНОВИК КАРТОЧКИ СИСТЕМЫ — кнопка «Собрать черновик карточки системы по базе» в блоке «Для аудита» боковой панели (mint/cards.py)":
        "SYSTEM CARD DRAFT — the “Draft a system card from the base” button in the “For the review” block of the sidebar (mint/cards.py)",
    "check_citations() факт без ссылки или со ссылкой мимо найденных фрагментов — пометка «⚠️ проверьте».":
        "check_citations()\na fact without a reference or with a reference outside the found fragments — marked “⚠️ check”.",
    "число систем; разделы — параллельно, не больше 3":
        "number of systems; sections — in parallel, at most 3",
    "Черновик карточки системы":
        "System card draft",
    "≈ 2 на раздел":
        "≈ 2 per section",
    "Сверка с эталоном compare_with_reference(): модель сверяет каждый пункт эталона с замечаниями аудита — то же место и суть: найдено, частично, пропущено; пачками, пропущенное переспрашивается → reference_markdown().":
        "Comparison with a reference\ncompare_with_reference(): the model matches each reference item against the review findings — the same place and substance: found, partial, missed; in batches, missing ones are asked again → reference_markdown().",
    "REDUCE: повторы model_findings() → collect_unique_findings() (основы ≥ 80 %, в кусках одного раздела — section_runs() — ≥ 40 %; steps_conflict() — разные шаги не склеиваются) → clean_typos() (без модели) → merge_duplicate_findings() (audit_merge_duplicates, +1 вызов): замечания одного ответа и о разных шагах не сливаются.":
        "REDUCE: duplicates\nmodel_findings() → collect_unique_findings() (stems ≥ 80 %, in the pieces of one section — section_runs() — ≥ 40 %; steps_conflict() — different steps are not joined) → clean_typos() (without the model) → merge_duplicate_findings() (audit_merge_duplicates, +1 call): findings of one answer and about different steps are not merged.",
    "run_audit() audit_cfg(): audit_reasoning — без выключателя рассуждений, max_tokens + 6000, таймаут ≥ 300 с; reasoning_on() — включатель в запросе. record_answers(): каждый запрос и ответ модели слово в слово.":
        "run_audit()\naudit_cfg(): audit_reasoning — without the reasoning switch-off, max_tokens + 6000, timeout ≥ 300 s; reasoning_on() — the switch-on in the request. record_answers(): every model request and answer word for word.",
    "Без карточек систем аудит не знает их возможностей и не может проверить, что документ требует от системы (answer_system) и не противоречит ли её ограничениям.":
        "Without system cards the review does not know what the systems can do and cannot check what the document requires from a system (answer_system) or whether it contradicts the system's limitations.",
    "«Главное» summary_candidates() → select_summary() (audit_summary_max, +1 вызов): модель-редактор выбирает важное и пишет суть строкой со ссылкой на номер; не ответила — _summary_fallback(): по подтверждению и критичности.":
        "“Key points”\nsummary_candidates() → select_summary() (audit_summary_max, +1 call): an editor model picks what matters and writes the gist in a line with a pointer to the number; no answer — _summary_fallback(): by corroboration and severity.",
    "Ближайшие к разделу фрагменты; 0 — не передавать.":
        "The fragments closest to the section; 0 — do not pass.",
    "Документы-основания: документы базы по ссылкам на титуле и в «Ссылочных документах» — в каждой проверке раздела.":
        "Basis documents: base documents by the references on the title page and in “Referenced documents” — in every section check.",
    "Фрагменты документов-оснований на один запрос аудита (сверх норм поиска).":
        "Fragments of basis documents per review request (on top of the search norms).",
    "Без вызовов LLM; что найдено — блок «📎 Документы-основания» на вкладке и лог; снять или добавить — там же.":
        "No LLM calls; what was found — the “📎 Basis documents” block on the tab and the log; remove or add there.",
}
