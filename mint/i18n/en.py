"""English translations of interface strings: Russian source text → English.

Generated from the tr() / N_() calls in the code and edited by hand. tests/test_i18n.py checks that every
string has a translation with the same {placeholders}."""

EN = {
    # ---- mint/audit.py
    'КРИТИЧНЫЙ':
        'CRITICAL',
    'СРЕДНИЙ':
        'MEDIUM',
    'НИЗКИЙ':
        'LOW',
    'без пояснения':
        'no reason given',
    'Часть чистая':
        'Section is clean',
    '🔥 **[КРИТИЧНЫЙ]**':
        '🔥 **[CRITICAL]**',
    '⚠️ **[СРЕДНИЙ]**':
        '⚠️ **[MEDIUM]**',
    '📝 **[НИЗКИЙ]**':
        '📝 **[LOW]**',
    '⚠️ ДОКУМЕНТ ТРЕБУЕТ ДОРАБОТКИ. ':
        '⚠️ THE DOCUMENT NEEDS REWORK. ',
    'Выявлены критические замечания.':
        'Critical findings identified.',
    'Выявлены замечания.':
        'Findings identified.',
    '### ❓ В проверенных разделах замечаний не обнаружено.':
        '### ❓ No findings in the reviewed sections.',
    '### ✅ Замечаний не обнаружено.':
        '### ✅ No findings.',
    '✅ ДОКУМЕНТ СОГЛАСОВАН.':
        '✅ THE DOCUMENT IS APPROVED.',
    '⚠️ ПРОВЕРЕНО НЕ ПОЛНОСТЬЮ: не удалось проверить {n_failed_sections} из {n_sections} разделов — результат нельзя считать согласованием.':
        '⚠️ REVIEW INCOMPLETE: {n_failed_sections} of {n_sections} sections could not be reviewed — the result cannot be treated as an approval.',
    '\n## ⚠️ РАЗДЕЛЫ, КОТОРЫЕ НЕ УДАЛОСЬ ПРОВЕРИТЬ\n':
        '\n## ⚠️ SECTIONS THAT COULD NOT BE REVIEWED\n',
    '- Часть {n}/{n_sections} «{prev}»: {err}':
        '- Part {n}/{n_sections} “{prev}”: {err}',
    '# ЭКСПЕРТНОЕ ЗАКЛЮЧЕНИЕ\n**Объект анализа**: документ «{filename}»\n':
        '# EXPERT REVIEW REPORT\n**Subject**: document “{filename}”\n',
    '**Особое внимание**: {v}\n':
        '**Special attention**: {v}\n',
    '**Статус**: {verdict_text}\n\n':
        '**Status**: {verdict_text}\n\n',
    '# Лог проверки: {filename}':
        '# Review log: {filename}',
    '## Часть {part}/{total} — «{preview}»':
        '## Part {part}/{total} — “{preview}”',
    '**Не проверено:** {report}':
        '**Not reviewed:** {report}',
    '**Нормативные источники:** ':
        '**Reference sources:** ',
    '**Нормативные источники:** в базе не найдены':
        '**Reference sources:** none found in the knowledge base',
    '**Отклонено:**':
        '**Rejected:**',
    '\n⚠️ [ЗАМЕЧАНИЕ MINT]: {note}':
        '\n⚠️ [MINT FINDING]: {note}',
    '⚠️ Замечания MINT без привязки к тексту ({n_unbound})':
        '⚠️ MINT findings not tied to a place in the text ({n_unbound})',
    # ---- mint/citations.py
    '⚠️ Ссылки, которых нет среди найденных фрагментов ({n}): {refs}. Утверждения с этими ссылками проверьте по '
    'документам — модель могла их додумать.':
        '⚠️ References that are not among the retrieved fragments ({n}): {refs}. Check the statements with these '
        'references against the documents — the model may have made them up.',
    # ---- mint/config.py
    'встроенный разбор (python-dotenv не установлен)':
        'built-in parser (python-dotenv is not installed)',
    'config.yaml не прочитан: не установлен PyYAML (pip install pyyaml).':
        'config.yaml was not read: PyYAML is not installed (pip install pyyaml).',
    'config.yaml не прочитан ({v}) — используются значения по умолчанию.':
        'config.yaml was not read ({v}) — default values are used.',
    'config.yaml должен содержать параметры вида «имя: значение» — файл пропущен.':
        'config.yaml must contain parameters of the form “name: value” — the file is skipped.',
    'Параметр «{k}» в config.yaml не используется: подключения задаются в .env.':
        'Parameter “{k}” in config.yaml is not used: connections are set in .env.',
    'Неизвестный параметр «{k}» в config.yaml — пропущен.':
        'Unknown parameter “{k}” in config.yaml — skipped.',
    'Параметр «{k}»: неверное значение {v!r} — оставлено {v2!r}.':
        'Parameter “{k}”: invalid value {v!r} — kept {v2!r}.',
    'Не задан адрес языковой модели — укажите LLM_API_URL в файле .env.':
        'The language model address is not set — put LLM_API_URL into the .env file.',
    'Не задан адрес сервиса эмбеддингов — укажите EMBED_API_URL в файле .env.':
        'The embedding service address is not set — put EMBED_API_URL into the .env file.',
    # ---- mint/feedback.py
    '… [обрезано, всего {n_value} симв.]':
        '… [truncated, {n_value} characters in total]',
    # ---- mint/glossary.py
    'свой':
        'your own',
    'из документов':
        'from documents',
    'Сокращение':
        'Abbreviation',
    'Расшифровка':
        'Expansion',
    'Откуда':
        'Source',
    # ---- mint/kb.py
    'Не удалось сгенерировать векторы через сервис эмбеддингов.':
        'Could not get vectors from the embedding service.',
    'Размерность векторов текущей модели эмбеддингов ({dim}) не совпадает с базой ({d}): база построена другой моделью. Переиндексируйте базу (кнопка в списке документов) или верните прежнюю EMBED_MODEL.':
        'The vector dimension of the current embedding model ({dim}) does not match the knowledge base ({d}): the base was built with another model. Re-index the base (button in the document list) or switch back to the previous EMBED_MODEL.',
    'Успешно добавлено {v} векторов.':
        'Added {v} vectors.',
    ' Структура документа не распознана — заголовки не использованы (плоский режим).':
        ' The document structure was not recognised — headings are not used (flat mode).',
    ' Заголовки в документе не найдены (нет стилей «Заголовок»?) — привязка к разделам недоступна.':
        ' No headings found in the document (no “Heading” styles?) — linking to sections is not available.',
    ' Распознано заголовков: {n_headings}.':
        ' Headings recognised: {n_headings}.',
    ' ⚠️ Пропущено {n_skipped} из {n_total} чанков: не удалось получить эмбеддинг (по ним возможен только поиск BM25 через parent).':
        ' ⚠️ Skipped {n_skipped} of {n_total} chunks: no embedding received (they can only be found by BM25 through their parent).',
    '❌ Ошибка транзакции: {v}':
        '❌ Transaction error: {v}',
    'параметры индексации не записаны (документ загружен до v18)':
        'indexing parameters are not recorded (document uploaded before v18)',
    'проиндексирован моделью эмбеддингов «{v}», сейчас — «{embed_model}»: векторный поиск по нему не работает':
        'indexed with the embedding model “{v}”, current model is “{embed_model}”: vector search does not work for it',
    'нарезан с другими параметрами: ':
        'chunked with different parameters: ',
    'Сервис эмбеддингов недоступен — переиндексация не начата.':
        'The embedding service is unavailable — re-indexing was not started.',
    # ---- mint/limits.py
    'Окно контекста LLM, токенов':
        'LLM context window, tokens',
    'Вход модели эмбеддингов, токенов':
        'Embedding model input, tokens',
    'Вход реранкера (запрос + документ), токенов':
        'Reranker input (query + document), tokens',
    'Символов текста на токен':
        'Characters of text per token',
    'Фрагмент в контексте чата':
        'Fragment in the chat context',
    'Parent-фрагмент (индексация)':
        'Parent fragment (indexing)',
    'Перекрытие parent':
        'Parent overlap',
    'Child-фрагмент (индексация)':
        'Child fragment (indexing)',
    'Перекрытие child':
        'Child overlap',
    'Раздел документа для эмбеддинга (вкладка 3)':
        'Document section for embedding (tab 3)',
    'Запрос к базе из раздела документа':
        'Knowledge base query from a document section',
    'Раздел документа на одну проверку':
        'Document section per review call',
    'Нормативный контекст в аудите':
        'Reference context in the review',
    'Фрагменты новой редакции на замечание':
        'Fragments of the new revision per review comment',
    'Запрос для реранкера':
        'Query for the reranker',
    'Фрагмент документа для реранкера':
        'Document fragment for the reranker',
    'ответ не похож на OpenAI-совместимый API (не JSON)':
        'the response does not look like an OpenAI-compatible API (not JSON)',
    'эмбеддинги':
        'embeddings',
    'вручную':
        'manual',
    'измерено':
        'measured',
    'сервер':
        'server',
    'типовое значение':
        'typical value',
    'авто: {preset}':
        'auto: {preset}',
    'не нужен':
        'not needed',
    'авто':
        'auto',
    '«{label}» = {value} ({source}) больше рассчитанного потолка {v}: текст может не поместиться во вход модели.':
        '“{label}” = {value} ({source}) exceeds the computed ceiling {v}: the text may not fit into the model input.',
    '«{label}»: модели слишком мало места (потолок {v}), взят минимум {auto}. Возьмите модель с бо́льшим окном или уменьшите Top-K / длину ответа.':
        '“{label}”: too little room for the model (ceiling {v}), the minimum {auto} is used. Choose a model with a larger window or reduce Top-K / the answer length.',
    # ---- mint/prompts.py
    # ---- mint/review.py
    '❓ Не удалось проверить':
        '❓ Could not verify',
    'Ответ модели не удалось разобрать: {raw}':
        "The model's answer could not be parsed: {raw}",
    '❌ Не исправлено':
        '❌ Not fixed',
    '✅ Исправлено':
        '✅ Fixed',
    '⚠️ Частично':
        '⚠️ Partially fixed',
    '{comment} Цитата из новой редакции: «{quote}»':
        '{comment} Quote from the new revision: “{quote}”',
    'Модель выставила «{status}», но цитата не найдена в тексте новой редакции — проверьте вручную. {comment} Цитата модели: «{quote}»':
        "The model returned “{status}”, but the quote was not found in the new revision — check manually. {comment} The model's quote: “{quote}”",
    'Неожиданный статус в ответе модели: {raw}':
        "Unexpected status in the model's answer: {raw}",
    'Не удалось подобрать релевантные разделы новой редакции (поиск недоступен или документ пуст).':
        'Could not find relevant sections of the new revision (search unavailable or the document is empty).',
    '# МАТРИЦА КОНТРОЛЯ УСТРАНЕНИЯ ЗАМЕЧАНИЙ\n\n':
        '# REVIEW COMMENT RESOLUTION MATRIX\n\n',
    '| № | Замечание | Статус ИИ | Заключение |':
        '| # | Review comment | AI status | Conclusion |',
    'МАТРИЦА КОНТРОЛЯ УСТРАНЕНИЯ ЗАМЕЧАНИЙ':
        'REVIEW COMMENT RESOLUTION MATRIX',
    'Дата выгрузки отчета: {date}':
        'Report date: {date}',
    'Файл: {filename}':
        'File: {filename}',
    'Замечание архитектора':
        "Reviewer's comment",
    'Статус ИИ':
        'AI status',
    'Анализ исправления в новой редакции':
        'Analysis of the fix in the new revision',
    # ---- mint/search.py
    'Временный сбой поиска. Проводится автономный анализ текста.':
        'Temporary search failure. Analysing the text without the knowledge base.',
    'База знаний пуста.':
        'The knowledge base is empty.',
    'В базе знаний ничего не найдено.':
        'Nothing found in the knowledge base.',
    'итог {v:.4f}':
        'total {v:.4f}',
    'rerank {r_score:.2f} (не учтён)':
        'rerank {r_score:.2f} (not counted)',
    'таблица':
        'table',
    'склеено соседних фрагментов: {n}':
        'adjacent fragments joined: {n}',
    # ---- mint/services.py
    'проверка сертификатов отключена (SSL_INSECURE=1)':
        'certificate verification is disabled (SSL_INSECURE=1)',
    'сертификаты: {tls_verify}':
        'certificates: {tls_verify}',
    'сертификаты: хранилище ОС (truststore)':
        'certificates: OS certificate store (truststore)',
    'сертификаты: набор certifi — внутренний CA компании в нём не найдётся; укажите CA_BUNDLE_PATH или установите пакет truststore':
        "certificates: certifi bundle — your organisation's internal CA is not in it; set CA_BUNDLE_PATH or install the truststore package",
    'не подключён (необязательно)':
        'not connected (optional)',
    'доступен':
        'available',
    '❌ [ОШИБКА НАСТРОЙКИ]: не задан LLM_API_URL в файле .env.':
        '❌ [CONFIGURATION ERROR]: LLM_API_URL is not set in the .env file.',
    '❌ [ОШИБКА НАСТРОЙКИ]: не выбрана модель — задайте LLM_MODEL в .env или выберите модель в панели.':
        '❌ [CONFIGURATION ERROR]: no model selected — set LLM_MODEL in .env or choose a model in the sidebar.',
    '❌ [КОНТЕКСТ НЕ ПОМЕЩАЕТСЯ]: запрос ≈ {est_input} токенов при окне модели {llm_context_tokens}. Уменьшите глубину поиска (Top-K) или размеры фрагментов.':
        '❌ [CONTEXT DOES NOT FIT]: the request is ≈ {est_input} tokens with a model window of {llm_context_tokens}. Reduce the search depth (Top-K) or the fragment sizes.',
    '❌ [ОШИБКА ДОСТУПА]: шлюз вернул {status_code}. Проверьте LLM_API_KEY.':
        '❌ [ACCESS ERROR]: the gateway returned {status_code}. Check LLM_API_KEY.',
    '❌ [ОШИБКА ИНФРАСТРУКТУРЫ MINT]: лимиты/шлюз после {max_retries} попыток (HTTP {status_code}).':
        '❌ [MINT INFRASTRUCTURE ERROR]: rate limits / gateway after {max_retries} attempts (HTTP {status_code}).',
    '❌ [ОТВЕТ ОБРЕЗАН]: модель израсходовала лимит {chosen_tokens} токенов (вероятно, на рассуждения) и не дала ответа. Увеличьте «Макс. длину ответа модели» в блоке «Модели и лимиты» или выберите модель без рассуждений.':
        '❌ [ANSWER TRUNCATED]: the model used up the limit of {chosen_tokens} tokens (probably on reasoning) and gave no answer. Increase “Max answer length” in the “Models and limits” block or choose a model without reasoning.',
    '\n\n⚠️ Ответ обрезан: достигнут лимит длины ответа ({chosen_tokens} токенов). Увеличьте «Макс. длину ответа модели» в блоке «Модели и лимиты».':
        '\n\n⚠️ Answer truncated: the answer length limit was reached ({chosen_tokens} tokens). Increase “Max answer length” in the “Models and limits” block.',
    '❌ [ОШИБКА СТРУКТУРЫ]: Некорректный формат JSON-ответа от модели.':
        '❌ [FORMAT ERROR]: invalid JSON response from the model.',
    '❌ [ОШИБКА ШЛЮЗА]: Сервер вернул код {status_code}: {v}':
        '❌ [GATEWAY ERROR]: the server returned code {status_code}: {v}',
    '❌ [СЕТЕВОЙ СБОЙ MINT]: Не удалось достучаться до модели ИИ ({v}).':
        '❌ [MINT NETWORK FAILURE]: could not reach the AI model ({v}).',
    '❌ [ОШИБКА]: Запрос к языковой модели аварийно завершен.':
        '❌ [ERROR]: the request to the language model failed.',
    'ошибка сертификата TLS — укажите в .env CA_BUNDLE_PATH (корпоративный сертификат) или, только во внутренней сети, SSL_INSECURE=1':
        'TLS certificate error — set CA_BUNDLE_PATH (corporate certificate) in .env or, only in an internal network, SSL_INSECURE=1',
    'сервер {host} не ответил вовремя':
        'server {host} did not respond in time',
    'нет соединения с {v}: адрес неверен, сервер выключен или закрыт сетью':
        'no connection to {v}: wrong address, server is down or blocked by the network',
    'неверный адрес «{url}» — нужен вид https://host/v1':
        'invalid address “{url}” — expected the form https://host/v1',
    'HTTP {code}: доступ запрещён — проверьте ключ (LLM_API_KEY / EMBED_API_KEY / RERANK_API_KEY)':
        'HTTP {code}: access denied — check the key (LLM_API_KEY / EMBED_API_KEY / RERANK_API_KEY)',
    'HTTP 404: по адресу {url} ничего нет — проверьте адрес в .env':
        'HTTP 404: nothing at {url} — check the address in .env',
    # ---- mint/ui/app.py
    # ---- ui/theme.py
    'База знаний пока пуста. Добавьте документы на боковой панели («Добавить регламенты в базу») — и задавайте вопросы: ответ придёт со ссылками на разделы.':
        'The knowledge base is empty. Add documents in the sidebar (“Add reference documents to the base”), then ask questions: answers come with links to the sections.',
    'Документов в базе: {n}. Задайте вопрос — ответ придёт со ссылками на разделы, из которых он взят.':
        'Documents in the base: {n}. Ask a question — the answer comes with links to the sections it is taken from.',
    'и ещё {n}': 'and {n} more',
    'Интеллектуальная RAG-система: ответы по базе знаний, аудит документов и контроль исправлений — со ссылками на источники':
        'An intelligent RAG system: answers from your knowledge base, document review and verification of fixes — with links to the sources',
    'Требует доработки':
        'Needs rework',
    'Есть замечания':
        'Findings to address',
    'Проверено не полностью':
        'Review incomplete',
    'Согласовано':
        'Approved',
    'Не удалось проверить разделов: {n_failed} из {n_sections} — результат нельзя считать согласованием.':
        '{n_failed} of {n_sections} sections could not be reviewed — the result is not an approval.',
    'критичные':
        'critical',
    'средние':
        'medium',
    'низкие':
        'low',
    'Есть неисправленные':
        'Not all fixed',
    'Исправлено не всё':
        'Partly fixed',
    'Всё исправлено':
        'All fixed',
    'исправлено':
        'fixed',
    'частично':
        'partially',
    'не исправлено':
        'not fixed',
    'не удалось проверить':
        'could not verify',
    '💬 Интерактивный чат (RAG)':
        '💬 Interactive chat (RAG)',
    '📋 Аудит документа':
        '📋 Document review',
    '🔄 Контроль исправления замечаний':
        '🔄 Verification of fixes',
    # ---- mint/ui/common.py
    '⚙️ Лог проверки: Часть {part}/{total} -> «{preview}»':
        '⚙️ Review log: part {part}/{total} -> “{preview}”',
    'Нормативные источники: ':
        'Reference sources: ',
    'Нормативный контекст в базе не найден.':
        'No reference context found in the knowledge base.',
    'Отклонено: ':
        'Rejected: ',
    'Сколько токенов модель принимает целиком: промпт, найденные фрагменты и ответ. Указано в описании модели (context window / max_model_len). Если окно маленькое, MINT уменьшит фрагменты и объём контекста, чтобы запрос не обрезался.':
        'How many tokens the model accepts in total: prompt, retrieved fragments and answer. See the model description (context window / max_model_len). If the window is small, MINT shrinks fragments and the context so that requests are not truncated.',
    'Максимальная длина текста, которую принимает модель эмбеддингов (max input / max_seq_len). От неё зависят размер child-фрагмента и длина запроса.':
        'Maximum text length accepted by the embedding model (max input / max_seq_len). It determines the child fragment size and the query length.',
    'Максимальная длина пары «запрос + документ» у реранкера (max_length). От неё зависит, сколько текста документа видит реранкер.':
        'Maximum length of a “query + document” pair for the reranker (max_length). It determines how much of each document the reranker sees.',
    'Сколько символов текста приходится на один токен. Зависит от токенизатора модели и языка (обычно 2–4; русский текст «дороже» английского). Кнопка «Определить у сервера» измеряет его на языке базы знаний: для русской базы — на русском тексте, для английской — на английском, для смешанной или пустой — на обоих и берёт меньшее. Загрузили документы на другом языке — определите заново.':
        "How many characters of text make one token. Depends on the model's tokenizer and the language (usually 2–4; "
        "Russian text takes more tokens than English). The “Detect from server” button measures it in the language "
        "of the knowledge base: on Russian text for a Russian base, on English text for an English one, and on both "
        "for a mixed or empty base, taking the lower value. After uploading documents in another language, detect "
        "it again.",
    '🧠 Языковая модель':
        '🧠 Language model',
    'Таймаут ответа LLM (сек)':
        'LLM response timeout (s)',
    'Сколько секунд ждать ответ модели на одну попытку. Для длинных ответов и моделей с рассуждениями — больше.':
        "How many seconds to wait for the model's answer per attempt. Increase for long answers and reasoning models.",
    'Число попыток обращения к LLM':
        'Number of LLM attempts',
    'Сколько раз повторять запрос при таймауте или ошибках шлюза (429/502/503/504). Пауза между попытками растёт.':
        'How many times to retry on a timeout or gateway errors (429/502/503/504). The pause between attempts grows.',
    '📂 Индексация — действует на документы, загруженные после изменения':
        '📂 Indexing — applies to documents uploaded after the change',
    'Parent-фрагмент (симв.)':
        'Parent fragment (chars)',
    'Крупный фрагмент, который уходит в контекст LLM. Больше — связнее контекст, но дороже и шумнее. Уже загруженные документы не меняются: для применения переиндексируйте их.':
        'A large fragment that goes into the LLM context. Larger means more coherent context, but more expensive and noisier. Already uploaded documents do not change: re-index them to apply.',
    'Перекрытие parent (симв.)':
        'Parent overlap (chars)',
    'Сколько символов повторяется между соседними parent-фрагментами, чтобы мысль не обрывалась на границе.':
        'How many characters are repeated between neighbouring parent fragments so that a thought is not cut at the border.',
    'Child-фрагмент (симв.)':
        'Child fragment (chars)',
    'Мелкий фрагмент для векторного поиска. Меньше — точнее поиск по смыслу, но меньше контекста в одном векторе.':
        'A small fragment for vector search. Smaller means more precise semantic search, but less context per vector.',
    'Перекрытие child (симв.)':
        'Child overlap (chars)',
    'Сколько символов повторяется между соседними child-фрагментами.':
        'How many characters are repeated between neighbouring child fragments.',
    '🔎 Поиск и контекст':
        '🔎 Search and context',
    'Макс. длина фрагмента в контексте LLM (симв.)':
        'Max fragment length in the LLM context (chars)',
    'Сколько символов каждого найденного фрагмента передаётся модели; длиннее — обрезается по границе предложения. Должно быть не меньше размера parent-фрагмента, иначе конец фрагмента теряется.':
        'How many characters of each retrieved fragment are passed to the model; longer ones are cut at a sentence boundary. Should be at least the parent fragment size, otherwise the end of the fragment is lost.',
    'Кандидатов из векторного поиска (dense)':
        'Candidates from vector search (dense)',
    'Сколько ближайших child-фрагментов берётся из векторного поиска до группировки по parent. Больше — выше полнота.':
        'How many nearest child fragments are taken from vector search before grouping by parent. More means higher recall.',
    'Кандидатов из BM25':
        'Candidates from BM25',
    'Сколько parent-фрагментов берётся из поиска по словам (BM25).':
        'How many parent fragments are taken from keyword search (BM25).',
    'Кандидатов после слияния':
        'Candidates after merging',
    'Сколько лучших кандидатов после слияния dense и BM25 идёт на реранк (все — при подключённом реранкере) и в итоговый отбор.':
        'How many best candidates after merging dense and BM25 go to reranking (all of them if a reranker is connected) and to the final selection.',
    'Макс. частей одной таблицы в контексте':
        'Max parts of one table in the context',
    'Большая таблица режется на части. Параметр не даёт частям одной таблицы вытеснить другие документы (лимит мягкий: свободные места добираются частями). 0 — без ограничения.':
        'A large table is split into parts. This keeps parts of one table from crowding out other documents (a soft limit: free slots are filled with parts). 0 — no limit.',
    '🔍 Multi-query (+1 вызов LLM)':
        '🔍 Multi-query (+1 LLM call)',
    'Перед поиском LLM формулирует альтернативный вариант вопроса; кандидаты берутся по обеим формулировкам.':
        'Before searching, the LLM writes an alternative wording of the question; candidates are taken for both wordings.',
    'Вес альтернативной формулировки':
        'Weight of the alternative wording',
    'С каким весом результаты по альтернативной формулировке идут в слияние (у исходной — 1.0).':
        'Weight with which results for the alternative wording enter the merge (the original has 1.0).',
    '🎯 Реранкер':
        '🎯 Reranker',
    'Документов в одном запросе':
        'Documents per request',
    'Ограничение шлюза: сколько документов отправлять в одном запросе. Остальные кандидаты уходят следующими запросами. При ошибке HTTP 400 от шлюза — уменьшайте.':
        'Gateway limit: how many documents to send in one request. Remaining candidates go in the next requests. Decrease if the gateway returns HTTP 400.',
    'Запрос для реранкера (симв.)':
        'Query for the reranker (chars)',
    'Сколько символов вопроса (с расшифровками сокращений) видит реранкер.':
        'How many characters of the question (with abbreviation expansions) the reranker sees.',
    'Фрагмент документа для реранкера (симв.)':
        'Document fragment for the reranker (chars)',
    'Реранкер получает не начало документа, а его самую релевантную часть такой длины (вместе с именем файла и разделом): найденный векторным поиском child-фрагмент с окружением или окно с наибольшей плотностью слов запроса.':
        'The reranker gets not the beginning of a document but its most relevant part of this length (with the file name and section): the child fragment found by vector search with its surroundings, or the window densest in query words.',
    'Символов в одном запросе':
        'Characters per request',
    'Ограничение шлюза: суммарный объём документов в одном запросе к реранкеру. Не поместившиеся кандидаты уходят следующим запросом.':
        'Gateway limit: total size of documents in one reranker request. Candidates that do not fit go in the next request.',
    'Имя файла и раздел в тексте для реранкера':
        'File name and section in the reranker text',
    'В начало текста для реранкера добавляются имя файла, раздел и название таблицы.':
        'The file name, section and table title are added at the start of the text for the reranker.',
    'Порог «голоса» реранкера':
        'Reranker “vote” threshold',
    'Балл реранкера учитывается, только если он не ниже порога; документы с меньшим баллом не удаляются. Порог подобран под шкалу bge-reranker (0…1): для другого реранкера его нужно проверить.':
        'A reranker score counts only if it is not below the threshold; documents with a lower score are not removed. Tuned for the bge-reranker scale (0…1): check it for another reranker.',
    '⚖️ Слияние результатов (взвешенный RRF)':
        '⚖️ Merging results (weighted RRF)',
    'Вес векторного поиска':
        'Vector search weight',
    'Влияние векторного поиска на итоговый порядок. 0 — канал отключён.':
        'Influence of vector search on the final order. 0 — the channel is off.',
    'Вес BM25':
        'BM25 weight',
    'Влияние поиска по словам на итоговый порядок. 0 — канал отключён.':
        'Influence of keyword search on the final order. 0 — the channel is off.',
    'Вес реранкера':
        'Reranker weight',
    'Влияние реранкера. Меньше весов dense и BM25 — реранкер может поднять документ, но не утопит найденный ими. 0 — порядок как без реранкера, но его баллы по-прежнему решают, ставить ли «уверенность низкая».':
        'Influence of the reranker. Below the dense and BM25 weights, the reranker can lift a document but not sink '
        'one they found. 0 — the order is as without the reranker, but its scores still decide whether to mark '
        '“low confidence”.',
    'Константа RRF':
        'RRF constant',
    'Сглаживание: чем больше, тем меньше разница между 1-м и 10-м местом в списке канала. Стандарт — 60.':
        "Smoothing: the larger it is, the smaller the difference between 1st and 10th place in a channel's list. Standard — 60.",
    '🚦 Уверенность и источники':
        '🚦 Confidence and sources',
    'Порог: балл реранкера':
        'Threshold: reranker score',
    'С реранкером пометка «уверенность низкая» ставится, если лучший балл реранкера ниже порога. Реранкер лучше других признаков отличает вопросы, ответа на которые в базе нет. Порог под свою базу подбирает eval_search.py.':
        'With a reranker, “low confidence” is marked when the best reranker score is below the threshold. The '
        'reranker tells questions without an answer in the knowledge base apart better than the other signals. '
        'eval_search.py finds the threshold for your base.',
    'Порог: доля слов вопроса в контексте':
        'Threshold: share of question words in the context',
    'Только без реранкера: пометка «уверенность низкая» ставится, если доля значимых слов вопроса в собранном контексте ниже порога и dense с BM25 не сошлись в топ-N.':
        'Only without a reranker: “low confidence” is marked when the share of significant question words in the '
        'assembled context is below the threshold and dense and BM25 do not agree in the top N.',
    'Порог: топ-N для согласия dense и BM25':
        'Threshold: top N for dense and BM25 agreement',
    'Только без реранкера: если выбранный документ есть в топ-N и у dense, и у BM25 — каналы согласны, и пометка не ставится.':
        'Only without a reranker: if a selected document is in the top N of both dense and BM25, the channels agree '
        'and the mark is not set.',
    'Показывать баллы в списке источников':
        'Show scores in the source list',
    'Итоговый балл, позиции в dense и BM25 и балл реранкера рядом с каждым источником.':
        'Total score, positions in dense and BM25 and the reranker score next to each source.',
    '💬 Чат':
        '💬 Chat',
    'Реплик истории для уточняющих вопросов':
        'History turns for follow-up questions',
    'Сколько предыдущих пар «вопрос — ответ» учитывать. Уточняющий вопрос («а для второго контура?») переписывается в самостоятельный по этой истории (+1 вызов LLM), а модель видит предыдущие реплики. 0 — каждый вопрос понимается отдельно.':
        'How many previous “question — answer” pairs to consider. A follow-up question (“and for the second circuit?”) is rewritten into a standalone one using this history (+1 LLM call), and the model sees the previous turns. 0 — every question is understood separately.',
    '📘 Глоссарий':
        '📘 Glossary',
    'Передавать модели справочник сокращений':
        'Pass the abbreviation list to the model',
    'Модель получает расшифровки сокращений из вопроса и найденных фрагментов и может использовать их в ответе.':
        'The model receives expansions of abbreviations from the question and the retrieved fragments and can use them in the answer.',
    'Сокращений в справочнике, не больше':
        'Max abbreviations in the list',
    'Сначала — сокращения из вопроса, затем из найденных фрагментов.':
        'First abbreviations from the question, then from the retrieved fragments.',
    'Раздел документа на одну проверку (симв.)':
        'Document section per review call (chars)',
    'Меньше — детальнее, но больше вызовов LLM; больше — меньше вызовов, но модель может пропустить замечания.':
        'Smaller means more detailed but more LLM calls; larger means fewer calls, but the model may miss findings.',
    'Запрос к базе из раздела документа (симв.)':
        'Knowledge base query from a document section (chars)',
    'Сколько символов начала раздела документа уходит в поиск норм по базе.':
        'How many characters from the start of a document section go into the search for norms.',
    'Нормативный контекст на раздел (симв.)':
        'Reference context per section (chars)',
    'Потолок объёма нормативных фрагментов (parent целиком, по релевантности), которые передаются модели вместе с разделом документа.':
        'Ceiling of the reference fragments (whole parents, by relevance) passed to the model together with a document section.',
    '🔄 Контроль исправлений':
        '🔄 Verification of fixes',
    'Разделов новой редакции на замечание':
        'Sections of the new revision per review comment',
    'Сколько самых релевантных разделов новой редакции передаётся модели для проверки одного замечания.':
        'How many of the most relevant sections of the new revision are passed to the model to check one review comment.',
    'Фрагменты новой редакции на замечание (симв.)':
        'Fragments of the new revision per review comment (chars)',
    'Потолок суммарного объёма разделов новой редакции на одно замечание.':
        'Ceiling of the total size of new-revision sections per review comment.',
    'Раздел документа для эмбеддинга (симв.)':
        'Document section for embedding (chars)',
    'Сколько символов раздела новой редакции уходит в модель эмбеддингов при подборе разделов.':
        'How many characters of a new-revision section go into the embedding model when selecting sections.',
    '\n\n**Рассчитано MINT:** {auto}':
        '\n\n**Computed by MINT:** {auto}',
    ' (потолок по лимитам моделей: {v})':
        ' (ceiling from the model limits: {v})',
    '\n\n**По умолчанию:** {v}.':
        '\n\n**Default:** {v}.',
    'Использованные источники':
        'Sources used',
    'итог':
        'total',
    'итог — суммарный взвешенный балл (RRF) · dense / BM25 — позиция в списке своего канала («—»: не найден этим каналом) · rerank ✓ — балл реранкера учтён, «не учтён» — ниже порога, «rerank —» — на реранк не отправлялся':
        "total — combined weighted score (RRF) · dense / BM25 — position in that channel's list (“—”: not found by this channel) · rerank ✓ — the reranker score is counted, “not counted” — below the threshold, “rerank —” — not sent to the reranker",
    # ---- mint/ui/feedback.py
    'ответы чата':
        'chat answers',
    'аудит':
        'review',
    'контроль исправлений':
        'verification of fixes',
    'Полезно, по делу':
        'Useful, to the point',
    'Неверно, неполно или не по делу':
        'Wrong, incomplete or off the point',
    '⚠️ Оценку не удалось записать в {v} — подробности в журнале MINT.':
        '⚠️ The rating could not be saved to {v} — see the MINT log for details.',
    '{mark} Спасибо! Оценка и комментарий записаны.':
        '{mark} Thank you! The rating and comment are saved.',
    'Что не так: ошибка, пропуск, лишнее, не тот источник?':
        'What is wrong: an error, something missed, something extra, the wrong source?',
    'Что особенно помогло?':
        'What helped most?',
    '{mark} Оценка записана. {question} (необязательно)':
        '{mark} Rating saved. {question} (optional)',
    'Комментарий для разработчика':
        'Comment for the developer',
    'Отправить комментарий':
        'Send comment',
    'Комментарий пустой — нечего отправлять.':
        'The comment is empty — nothing to send.',
    '💬 Отзывы: {total}':
        '💬 Feedback: {total}',
    'Оценивайте результаты кнопками 👍/👎 под ответами, заключением аудита и матрицей контроля — это главный источник улучшений MINT.':
        'Rate results with the 👍/👎 buttons under answers, review reports and verification matrices — this is the main source of improvements for MINT.',
    'Оценок пока нет. Они будут записываться в {v}.':
        'No ratings yet. They will be saved to {v}.',
    'Комментариев: {comments}':
        'Comments: {comments}',
    '⬇️ Скачать отзывы (feedback.jsonl)':
        '⬇️ Download feedback (feedback.jsonl)',
    'Перешлите файл разработчику MINT. В нём вопросы, ответы и цитаты из ваших документов — отправляйте только туда, куда можно передавать эти документы.':
        'Send the file to the MINT developer. It contains questions, answers and quotes from your documents — send it only where these documents may be shared.',
    'Файл: {v}':
        'File: {v}',
    # ---- mint/ui/sidebar.py
    '📄 .env прочитан: {env_files}':
        '📄 .env read: {env_files}',
    'Файл .env не найден. MINT ищет его здесь: ':
        'The .env file was not found. MINT looks for it here: ',
    ' и ':
        ' and ',
    '. Имя — ровно «.env» (без .txt и без .example).':
        '. The name must be exactly “.env” (without .txt or .example).',
    '📄 .env не найден — используются переменные окружения системы':
        '📄 .env not found — system environment variables are used',
    '🔑 Ключ API задан':
        '🔑 API key is set',
    '🔑 Ключ API не задан — подходит для локальных серверов без авторизации':
        '🔑 API key is not set — fine for local servers without authentication',
    '🎯 Реранкер: {r_desc}':
        '🎯 Reranker: {r_desc}',
    '🟢 Реранкер: доступен':
        '🟢 Reranker: available',
    '⚠️ Реранкер: {r_desc}':
        '⚠️ Reranker: {r_desc}',
    '❌ Реранкер: {r_desc}':
        '❌ Reranker: {r_desc}',
    '⚙️ Настройки':
        '⚙️ Settings',
    'Модель ИИ (LLM):':
        'AI model (LLM):',
    'Модель для ответов в чате и замечаний в аудите. Список запрашивается у сервера; модель по умолчанию задаётся в .env (LLM_MODEL).\n\n**По умолчанию:** {v}.':
        'The model for chat answers and review findings. The list is requested from the server; the default model is set in .env (LLM_MODEL).\n\n**Default:** {v}.',
    'сервер не вернул ни одной модели':
        'the server returned no models',
    'Список моделей не получен у сервера: {reason}. Если сервер не отдаёт список моделей, задайте модель в .env (LLM_MODEL).':
        'Could not get the model list from the server: {reason}. If the server does not provide a model list, set the model in .env (LLM_MODEL).',
    'Температура (креативность):':
        'Temperature (creativity):',
    'Чем ниже, тем ближе ответ к тексту регламентов; чем выше, тем больше вариативности и риск домыслов. Для регламентов обычно 0.0–0.2.\n\n**По умолчанию:** {temperature}.':
        'The lower, the closer the answer stays to the documents; the higher, the more variety and the risk of invention. For regulations usually 0.0–0.2.\n\n**Default:** {temperature}.',
    'Глубина поиска (Top-K):':
        'Search depth (Top-K):',
    'Сколько фрагментов попадёт в контекст модели. Больше — полнее ответ, но больше шума; при маленьком окне модели каждый фрагмент станет короче.\n\n**По умолчанию:** {auto_k} (4 при базе до 300 фрагментов, иначе 5).':
        "How many fragments go into the model's context. More means a fuller answer but more noise; with a small model window each fragment gets shorter.\n\n**Default:** {auto_k} (4 for a base of up to 300 fragments, otherwise 5).",
    '🧩 Модели и лимиты':
        '🧩 Models and limits',
    'От этих чисел MINT рассчитывает размеры фрагментов и объём контекста. Источник значения указан в подписи: config.yaml, сервер, типовое значение или вручную (на время сеанса).':
        'MINT derives fragment sizes and context budgets from these numbers. The source of each value is shown in its label: config.yaml, server, typical value or manual (for this session).',
    'Макс. длина ответа модели (токенов):':
        'Max answer length (tokens):',
    'Если ответы обрываются на полуслове — увеличьте. Моделям с рассуждениями (R1 и др.) нужен запас. Больше ответ — меньше места под найденные фрагменты.\n\n**По умолчанию:** {max_tokens}.':
        'If answers stop mid-sentence, increase it. Reasoning models (R1 etc.) need headroom. A longer answer leaves less room for retrieved fragments.\n\n**Default:** {max_tokens}.',
    '📏 Определить у сервера':
        '📏 Detect from server',
    'Спрашивает у сервера окна моделей и измеряет «символов на токен» короткими запросами на языке базы знаний. Значения, введённые вручную в этом блоке, сбрасываются.':
        'Asks the server for the model windows and measures “characters per token” with short requests in the language of the knowledge base. Values entered manually in this block are reset.',
    'Измеряю «символов на токен»...':
        'Measuring “characters per token”...',
    'окно LLM — {v}':
        'LLM window — {v}',
    'вход эмбеддингов — {v}':
        'embedding input — {v}',
    'вход реранкера — {v}':
        'reranker input — {v}',
    'символов на токен — {cpt} ({cpt_src}; {lang_note})':
        'characters per token — {cpt} ({cpt_src}; {lang_note})',
    'база на русском — измерено на русском тексте':
        'Russian knowledge base — measured on Russian text',
    'база на английском — измерено на английском тексте':
        'English knowledge base — measured on English text',
    'в базе русский и английский ({pct}% русского) — взято меньшее из двух':
        'the knowledge base mixes Russian and English ({pct}% Russian) — the lower of the two is used',
    'база пуста — взято меньшее из русского и английского':
        'the knowledge base is empty — the lower of Russian and English is used',
    'символов на токен — не измерено':
        'characters per token — not measured',
    '. Чего сервер не сообщает — введите вручную или запишите в config.yaml (раздел models). Значения из config.yaml важнее найденных у сервера.':
        '. Whatever the server does not report, enter manually or put into config.yaml (the models section). Values from config.yaml take precedence over those found at the server.',
    'Сервер: ':
        'Server: ',
    '**MINT рассчитал:**':
        '**Computed by MINT:**',
    ' (авто было бы {auto})':
        ' (auto would be {auto})',
    'нет':
        'no',
    'нет префикса':
        'none',
    'Префикс запроса для модели эмбеддингов ({embed_prefix_source}): {prefix_note}':
        'Query prefix for the embedding model ({embed_prefix_source}): {prefix_note}',
    '; префикс документов: «{embed_doc_prefix}»':
        '; document prefix: “{embed_doc_prefix}”',
    'Контекст чата: до ≈ {v:,} симв. (Top-K {top_k} × фрагмент {smart_truncate_chars}) · ⚙️ авто · 📄 config.yaml · ✋ вручную':
        'Chat context: up to ≈ {v:,} chars (Top-K {top_k} × fragment {smart_truncate_chars}) · ⚙️ auto · 📄 config.yaml · ✋ manual',
    '📊 В базе {n_lens} parent-фрагментов, самый длинный — {v} симв.; длиннее лимита (будут обрезаны): {over}.':
        '📊 The base has {n_lens} parent fragments, the longest is {v} chars; longer than the limit (will be truncated): {over}.',
    '🛠️ Экспертные настройки':
        '🛠️ Expert settings',
    'Любое значение можно изменить на время сеанса (✋ вручную). Постоянные значения — в config.yaml. Рассчитанные MINT параметры помечены «авто»: при ручном изменении расчёт для них отключается.':
        'Any value can be changed for this session (✋ manual). Permanent values go into config.yaml. Parameters computed by MINT are marked “auto”: changing one manually turns its computation off.',
    '↩️ Сбросить изменения сеанса':
        '↩️ Reset session changes',
    'Возвращает все параметры к config.yaml и расчёту MINT.':
        "Returns all parameters to config.yaml and MINT's computation.",
    '📘 Сокращения: {n_gl}':
        '📘 Abbreviations: {n_gl}',
    'Глоссарий связывает сокращение с расшифровкой («СЗИ» ↔ «средства защиты информации»): поиск находит документ и по сокращению, и по полной форме, а модель может расшифровать сокращение в ответе. Сокращения собираются из загруженных документов автоматически (перечни сокращений, «полная форма (СОКР)»). Свои расшифровки — в файле {name}; они важнее найденных.':
        'The glossary links an abbreviation to its expansion (“PKI” ↔ “public key infrastructure”): search finds a document by either form, and the model can expand the abbreviation in its answer. Abbreviations are collected from uploaded documents automatically (lists of abbreviations, “Full Form (ABBR)”). Your own expansions go into the file {name}; they take precedence over the ones found.',
    'Из документов: {auto_count} · свои: {manual_count}':
        'From documents: {auto_count} · your own: {manual_count}',
    ' · убрано своим файлом: {removed_count}':
        ' · removed by your file: {removed_count}',
    ' · свой файл: {glossary_file}':
        ' · your file: {glossary_file}',
    ' (нет)':
        ' (none)',
    'Найденное в документах хранится в базе (auto_glossary.json) и не пропадает при перезапуске. Свой файл нужен, только чтобы исправить, добавить или убрать записи.':
        'What is found in documents is stored in the knowledge base (auto_glossary.json) and survives restarts. Your own file is only needed to correct, add or remove entries.',
    '_как_пользоваться':
        '_how_to_use',
    'Оставьте в файле только исправленные и новые записи — остальное MINT найдёт в документах сам и будет обновлять при загрузке новых. Чтобы убрать ошибочную расшифровку, оставьте пустую строку: "АБВ": "". Сохраните файл рядом с программой под именем glossary.json (или укажите путь в GLOSSARY_PATH). Ключи, начинающиеся с «_», игнорируются.':
        'Keep only corrected and new entries in the file — MINT finds the rest in the documents itself and updates it when new ones are uploaded. To remove a wrong expansion, leave an empty string: "ABC": "". Save the file next to the program as glossary.json (or set its path in GLOSSARY_PATH). Keys starting with “_” are ignored.',
    '⬇️ Скачать для правки (glossary.json)':
        '⬇️ Download for editing (glossary.json)',
    'Весь текущий список с инструкцией в начале. Оставьте только то, что исправили или добавили, — иначе записи из документов перестанут обновляться.':
        'The whole current list with instructions at the top. Keep only what you corrected or added — otherwise entries from documents stop being updated.',
    '📥 Добавить регламенты в базу':
        '📥 Add reference documents to the base',
    '➕ Загрузить новые документы в базу':
        '➕ Upload more documents to the base',
    '📎 Выбрано файлов: **{n_kb_files}**':
        '📎 Files selected: **{n_kb_files}**',
    '🚀 Проиндексировать все файлы в базу знаний':
        '🚀 Index all files into the knowledge base',
    '⏳ Обрабатываю {v}/{n_kb_files}: **{name}**...':
        '⏳ Processing {v}/{n_kb_files}: **{name}**...',
    '📁 Документы в базе':
        '📁 Documents in the base',
    '🗑️ Удалено из базы: {names}':
        '🗑️ Removed from the base: {names}',
    'Не удалось удалить: {names}':
        'Could not remove: {names}',
    'Документов':
        'Documents',
    'Документов в базе знаний':
        'Documents in the knowledge base',
    'Векторов':
        'Vectors',
    'Векторов в индексе FAISS: по одному на каждый небольшой фрагмент текста, по которому идёт поиск':
        'Vectors in the FAISS index: one for every small text fragment the search works on',
    'Найти документ':
        'Find a document',
    '🔎 Поиск по названию':
        '🔎 Search by name',
    'Найдено: {n} из {total}':
        'Found: {n} of {total}',
    'Документов с таким названием нет.':
        'No documents with such a name.',
    '🗑️ Удалить из базы':
        '🗑️ Remove from the base',
    'Из базы удаляются фрагменты, векторы и сохранённый оригинал. Вернуть документ можно, только загрузив его заново.':
        'The fragments, vectors and the stored original are removed. To bring a document back, upload it again.',
    'Документы':
        'Documents',
    'Выберите документы':
        'Choose documents',
    'Удалить из базы документов: {n}? Это нельзя отменить.':
        'Remove {n} document(s) from the base? This cannot be undone.',
    'Отмена':
        'Cancel',
    'Удалить':
        'Remove',
    '🗑️ Удалить выбранные ({n})':
        '🗑️ Remove selected ({n})',
    '⛔ {n_bad} док. проиндексированы другой моделью эмбеддингов — векторный поиск по ним не работает. Переиндексируйте базу.':
        '⛔ {n_bad} doc(s) were indexed with another embedding model — vector search does not work for them. Re-index the base.',
    'ℹ️ {n_changed} док. нарезаны с другими параметрами или загружены до v18 (наведите на ℹ️). Это не ошибка; для единообразия — переиндексация.':
        'ℹ️ {n_changed} doc(s) were chunked with different parameters or uploaded before v18 (hover over ℹ️). This is not an error; re-index for consistency.',
    '🔄 Переиндексация':
        '🔄 Re-indexing',
    'Нужна после смены модели эмбеддингов или параметров нарезки. Переиндексируются документы, оригиналы которых сохранены (загруженные в v18 и новее). Документы, загруженные раньше, загрузите заново. Если сменилась размерность векторов, база строится заново, и документы без оригинала удаляются.':
        'Needed after changing the embedding model or the chunking parameters. Documents whose originals are stored (uploaded in v18 or later) are re-indexed. Upload older documents again. If the vector dimension changed, the base is rebuilt and documents without an original are removed.',
    'Переиндексировать нечего: ни у одного из {n_rows} док. нет сохранённого оригинала. Загрузите их заново через «Добавить документы в базу» — с теми же именами файлов, старые версии заменятся.':
        'Nothing to re-index: none of the {n_rows} doc(s) has a stored original. Upload them again via “Add documents to the base” — with the same file names, the old versions are replaced.',
    'Без оригинала: {v} док.':
        'Without original: {v} doc(s)',
    '🔄 Переиндексировать ({n_src} док.)':
        '🔄 Re-index ({n_src} doc(s))',
    'В базе знаний пока нет документов.':
        'The knowledge base has no documents yet.',
    # ---- mint/ui/tab_audit.py
    '🛡️ Экспертный аудит документа':
        '🛡️ Expert document review',
    'Загрузите документ на проверку — любой: договор, положение, отчёт, техническое задание, курсовую. MINT проверит каждый раздел по вашим критериям и по документам из базы знаний.':
        'Upload a document to review — any: a contract, a policy, a report, a specification, a thesis. MINT checks every section against your criteria and the documents in the knowledge base.',
    '🧠 Подключать нормативную базу при анализе':
        '🧠 Use the reference base in the analysis',
    'Для каждого раздела документа из базы подбираются нормативные фрагменты, и модель проверяет раздел с их учётом. Без базы аудит идёт только по тексту документа (быстрее, но без опоры на регламенты).':
        'For each section of the document, reference fragments are selected from the base and the model checks the section against them. Without the base the review relies only on the document text (faster, but not grounded in regulations).',
    '🎯 Особое внимание (необязательно):':
        '🎯 Special attention (optional):',
    'Например: интеграция с системой X; хранение и передача персональных данных; резервное копирование и время восстановления':
        'For example: integration with system X; storage and transfer of personal data; backup and recovery time',
    'То, что важно именно в этом документе. На каждый пункт модель отвечает отдельно, по всему документу (блок «Ответы на пункты особого внимания» в заключении); при проверке разделов эти места проверяются в первую очередь, а самокритика не удаляет замечания по ним без опровержения в тексте. Каждый пункт — с новой строки, через «;» или вопросом.':
        'What matters in this particular document. The model answers each point separately, from the whole document (the “Answers to the special attention points” block of the report); in the section reviews these places are checked first, and self-critique does not drop findings about them unless the text refutes them. Put each point on a new line, separate with “;” or write it as a question.',
    '📝 Общие критерии проверки:':
        '📝 General review criteria:',
    'Список проверок для каждого раздела — критерии профиля (боковая панель → «🧭 Профиль»). Можно сократить или переписать под конкретный документ; пустое поле заменяется общим аудитом.':
        'The list of checks for every section — the criteria of the profile (sidebar → “🧭 Profile”). Shorten or rewrite them for a specific document; an empty field means a general review.',
    "Файл '{name}' готов к проверке.":
        "File '{name}' is ready for review.",
    '🚀 Запустить аудит документа':
        '🚀 Start the document review',
    'Запущен конвейер смыслового аудита...':
        'Review pipeline started...',
    '🎯 Нормы по «особому вниманию»: ':
        '🎯 Norms for “special attention”: ',
    'в базе не найдены — пункты проверяются по тексту документа':
        'not found in the base — the points are checked against the document text',
    'Версия MINT':
        'MINT version',
    'Время':
        'Time',
    'Промпты':
        'Prompts',
    'Модель':
        'Model',
    'Нормативная база':
        'Reference base',
    'да':
        'yes',
    'Самокритика':
        'Self-critique',
    'Разделов':
        'Sections',
    'Размер раздела (audit_map_size)':
        'Section size (audit_map_size)',
    'Объём норм (audit_context_max_chars)':
        'Norms volume (audit_context_max_chars)',
    'Особое внимание':
        'Special attention',
    'Нормы по особому вниманию':
        'Norms for special attention',
    'Критерии':
        'Criteria',
    '🏁 Экспертиза завершена, но {n_failed_sections} из {n_sections} разделов не проверены':
        '🏁 Review finished, but {n_failed_sections} of {n_sections} sections were not reviewed',
    '🏁 Аналитическая экспертиза завершена!':
        '🏁 Review finished!',
    '## 📄 Итоговое экспертное заключение':
        '## 📄 Final review report',
    '⚙️ Лог проверки по разделам ({n_saved_log}):':
        '⚙️ Review log by section ({n_saved_log}):',
    '📥 Скачать заключение (.md)':
        '📥 Download the report (.md)',
    'Заключение_{name}.md':
        'Review_report_{name}.md',
    '📥 Скачать документ с замечаниями (.docx)':
        '📥 Download the document with findings (.docx)',
    'Аудит_MINT_{name}':
        'MINT_review_{name}',
    'Замечания добавлены примечаниями Word (текст документа не меняется) — каждое к одному месту: по цитате из самокритики или к абзацу с наибольшим совпадением слов. Замечания, которые не удалось однозначно привязать, — списком в начале документа.':
        'Findings are added as Word comments (the document text is not changed) — each one to a single place: by the quote from self-critique, or to the paragraph with the largest word overlap. Findings that could not be placed unambiguously are listed at the start of the document.',
    'примечаниями':
        'as comments',
    'вставками в текст':
        'inline in the text',
    'Привязано {how}: {v} (по цитате — {v2}); списком в начале: {v3}.':
        'Attached {how}: {v} (by quote — {v2}); listed at the start: {v3}.',
    '📥 Экспорт рецензии в Word недоступен: {error}':
        '📥 Word export of the review is unavailable: {error}',
    '📥 Скачать лог проверки (.md)':
        '📥 Download the review log (.md)',
    'Лог_проверки_{v}.md':
        'Review_log_{v}.md',
    'Настройки прогона и по каждому разделу: результат, нормативные источники, отклонённое самокритикой. Нужен для разбора пропусков при тестировании.':
        'Run settings and, for every section: the result, reference sources, what self-critique rejected. Useful for analysing misses during testing.',
    '**Оцените проверку:** найдены ли важные замечания, нет ли лишних и ошибочных?':
        '**Rate the review:** were the important findings found, are there extra or wrong ones?',
    # ---- mint/ui/theme.py: documents of the base
    'карточка системы':
        'system card',
    'правила экспертов: учитываются в каждом аудите':
        'expert rules: used in every review',
    'векторов: {n}':
        'vectors: {n}',
    'другая модель эмбеддингов — переиндексируйте':
        'another embedding model — re-index',
    'Документы в базе':
        'Documents in the base',
    # ---- mint/ui/tab_chat.py
    'Консультация по накопленным знаниям':
        'Ask your knowledge base',
    '➕ Новый чат':
        '➕ New chat',
    'Очищает историю: следующий вопрос будет понят без учёта предыдущих реплик.':
        'Clears the history: the next question will be understood without the previous turns.',
    'Задайте вопрос по базе знаний...':
        'Ask a question about the knowledge base...',
    '🔎 Искал по вашему вопросу и по уточнённому с учётом диалога: «{q}»':
        '🔎 Searched by your question and by the one clarified from the dialogue: “{q}”',
    'Ищу в базе знаний...':
        'Searching the knowledge base...',
    # ---- mint/ui/tab_review.py
    '🤖 Автоматическая контр-проверка устранения замечаний':
        '🤖 Automatic verification of fixes',
    'Вставьте список выданных замечаний и загрузите новую редакцию документа.':
        'Paste the list of review comments that were issued and upload the new revision of the document.',
    '🧠 Использовать базу знаний при верификации':
        '🧠 Use the knowledge base for verification',
    'Для каждого замечания дополнительно подтягиваются нормативные фрагменты из базы.':
        'For each review comment, reference fragments from the base are added as well.',
    '📝 Ранее выданные замечания (каждое с новой строки):':
        '📝 Review comments issued earlier (one per line):',
    'Пример:\n- [КРИТИЧНЫЙ] Не указано шифрование ГОСТ\n- [СРЕДНИЙ] Завышен SLA.':
        'Example:\n- [CRITICAL] Encryption is not specified\n- [MEDIUM] SLA is overstated.',
    'Каждое замечание с новой строки; строки короче {n} символов игнорируются.':
        'One review comment per line; lines shorter than {n} characters are ignored.',
    'Новая редакция документа, в которой нужно проверить устранение замечаний.':
        'The new revision of the document in which fixes should be verified.',
    "Документ '{name}' загружен.":
        "Document '{name}' uploaded.",
    '🔍 Запустить контр-проверку исправления дефектов':
        '🔍 Start the verification of fixes',
    'Сличение редакций...':
        'Comparing revisions...',
    '📜 Новая редакция разбита на {n_sections_v2} разделов.':
        '📜 The new revision is split into {n_sections_v2} sections.',
    '⚠️ Эмбеддинги разделов недоступны — фрагменты подбираются только по словам (BM25).':
        '⚠️ Section embeddings are unavailable — fragments are selected by words only (BM25).',
    '🏁 Контр-проверка завершена, но {n_unverified} из {n_final_matrix_data} замечаний не удалось проверить':
        '🏁 Verification finished, but {n_unverified} of {n_final_matrix_data} review comments could not be verified',
    '🏁 Контр-проверка завершена!':
        '🏁 Verification finished!',
    'Матрица_{name}.docx':
        'Matrix_{name}.docx',
    '## 📊 Результаты проверки':
        '## 📊 Verification results',
    '📥 Скачать матрицу контроля (.md)':
        '📥 Download the matrix (.md)',
    'Матрица_контроля_{name}.md':
        'Resolution_matrix_{name}.md',
    '📥 Скачать отчёт в Word (.docx)':
        '📥 Download the Word report (.docx)',
    'Матрица_контроля_{name}.docx':
        'Resolution_matrix_{name}.docx',
    '**Оцените контр-проверку:** верно ли определены статусы замечаний?':
        '**Rate the verification:** were the statuses of the review comments determined correctly?',
    # ---- check_install.py
    'Похоже, включена замкнутая программная среда (ЗПС): библиотеки из pip не подписаны и не загружаются. Это решает администратор (подпись библиотек или исключение) — обходить ЗПС не нужно.':
        'The closed software environment (ЗПС, Astra Linux) seems to be enabled: libraries from pip are not signed and do not load. Only an administrator can resolve this (by signing the libraries or adding an exception) — do not try to bypass it.',
    'Система':
        'System',
    'ОС: {v}':
        'OS: {v}',
    'ЗПС включена':
        'Closed software environment (ЗПС) is enabled',
    ' (виртуальное окружение)':
        ' (virtual environment)',
    'Python {v} — нужен {v2}.{v3} или новее':
        'Python {v} — {v2}.{v3} or newer is required',
    'Astra Linux 1.7 поставляется с Python 3.7: нужна Astra 1.8 (Python 3.11) или отдельно установленный Python. В Windows — Python 3.11/3.12 с python.org (вариант «для текущего пользователя»).':
        'Astra Linux 1.7 ships Python 3.7: you need Astra 1.8 (Python 3.11) or a separately installed Python. On Windows — Python 3.11/3.12 from python.org (the “Install for me only” option).',
    'интерфейс':
        'interface',
    'разбор .docx':
        '.docx parsing',
    'векторный индекс':
        'vector index',
    'запросы к API':
        'API requests',
    'замечания в Word':
        'Word comments',
    'промпты моделей и config.yaml':
        'model prompts and config.yaml',
    'без него .env читается встроенным разбором — это нормально':
        'without it .env is read by the built-in parser — that is fine',
    'корпоративные сертификаты из хранилища ОС (важно для Windows)':
        'corporate certificates from the OS store (important on Windows)',
    'Пакеты Python':
        'Python packages',
    'Установите: pip install {dist}':
        'Install: pip install {dist}',
    '{dist} не загружается':
        '{dist} does not load',
    'Нужен 1.2+, иначе замечания в Word вставляются в текст, а не примечаниями: pip install -U python-docx':
        'Version 1.2+ is needed, otherwise findings are inserted into the Word text instead of comments: pip install -U python-docx',
    'Разбор .docx (Docling)':
        'Parsing .docx (Docling)',
    'модуль разбора MINT не загружается':
        "MINT's parsing module does not load",
    'не удалось создать тестовый .docx (python-docx)':
        'could not create a test .docx (python-docx)',
    'Docling пытается скачать модели из интернета. Скачайте их на машине с доступом (docling-tools models download), перенесите папку и укажите её в DOCLING_ARTIFACTS_PATH.':
        'Docling tries to download models from the internet. Download them on a machine with access (docling-tools models download), copy the folder and point DOCLING_ARTIFACTS_PATH to it.',
    'Docling не разобрал тестовый документ':
        'Docling failed to parse the test document',
    'тестовый .docx разобран за {dt:.1f} с':
        'test .docx parsed in {dt:.1f} s',
    'заголовок и таблица на месте':
        'heading and table are in place',
    ' (первый запуск обычно дольше)':
        ' (the first run is usually slower)',
    'Docling вернул неожиданный текст':
        'Docling returned unexpected text',
    'Настройки (.env, config.yaml)':
        'Settings (.env, config.yaml)',
    'настройки MINT не загружаются':
        'MINT settings do not load',
    '.env прочитан: {files}':
        '.env read: {files}',
    'разбор: {env_parser}':
        'parser: {env_parser}',
    '.env не найден':
        '.env not found',
    'Искал: ':
        'Looked in: ',
    '\n         Скопируйте .env.example в .env рядом с app.py и заполните (имя файла — ровно «.env»).':
        '\n         Copy .env.example to .env next to app.py and fill it in (the file name must be exactly “.env”).',
    'LLM: {v}  модель: {v2}':
        'LLM: {v}  model: {v2}',
    'Эмбеддинги: {v}  модель: {embed_model}':
        'Embeddings: {v}  model: {embed_model}',
    'Реранкер: {v}':
        'Reranker: {v}',
    '  модель: {rerank_model}':
        '  model: {rerank_model}',
    'Ключ LLM_API_KEY: ':
        'LLM_API_KEY: ',
    'задан':
        'set',
    'не задан (нормально для серверов без авторизации)':
        'not set (fine for servers without authentication)',
    'Папки':
        'Folders',
    'База знаний (KB_DIR)':
        'Knowledge base (KB_DIR)',
    'Логи и отзывы (LOG_DIR)':
        'Logs and feedback (LOG_DIR)',
    'папки ещё нет — MINT создаст её при первой записи':
        'the folder does not exist yet — MINT creates it on the first write',
    '{title}: {p} — нет прав на запись':
        '{title}: {p} — no write permission',
    'Проверьте права на {base} или укажите другую папку в .env':
        'Check the permissions on {base} or set another folder in .env',
    'В базе: документов {v}, векторов {v2}, размерность {v3}, записана MINT {v4}':
        'In the base: {v} documents, {v2} vectors, dimension {v3}, written by MINT {v4}',
    'manifest.json базы не читается':
        "the base's manifest.json cannot be read",
    'Связь с моделями':
        'Model connections',
    'LLM: сервер отвечает, моделей: {n_models}':
        'LLM: the server responds, models: {n_models}',
    'модели {llm_model} нет в списке сервера':
        "model {llm_model} is not in the server's list",
    'Проверьте LLM_MODEL в .env':
        'Check LLM_MODEL in .env',
    'LLM: список моделей не получен':
        'LLM: model list not received',
    'Сервер не отдаёт /models — это допустимо, если ответ модели ниже работает.':
        'The server does not provide /models — that is fine if the model answer below works.',
    'LLM: ответ не получен':
        'LLM: no answer received',
    'LLM ответила за {v:.1f} с':
        'LLM answered in {v:.1f} s',
    'Эмбеддинги: HTTP {status_code}':
        'Embeddings: HTTP {status_code}',
    'Эмбеддинги: ответ без вектора':
        'Embeddings: response without a vector',
    'Эмбеддинги: вектор размерности {n_vec}':
        'Embeddings: vector of dimension {n_vec}',
    'база построена другой моделью эмбеддингов (размерность {kb_dim})':
        'the base was built with another embedding model (dimension {kb_dim})',
    'Верните прежнюю EMBED_MODEL или переиндексируйте базу в интерфейсе.':
        'Switch back to the previous EMBED_MODEL or re-index the base in the interface.',
    'Эмбеддинги: нет связи':
        'Embeddings: no connection',
    'Реранкер: {desc}':
        'Reranker: {desc}',
    'Поиск работает и без реранкера, но точность ниже.':
        'Search works without a reranker, but accuracy is lower.',
    'Запуск':
        'Start',
    'Streamlit слушает только этот компьютер (localhost)':
        'Streamlit listens on this computer only (localhost)',
    'нет .streamlit/config.toml с address = "localhost"':
        'no .streamlit/config.toml with address = "localhost"',
    'Без него страница MINT доступна по сети всем, кто знает адрес компьютера.':
        "Without it the MINT page is reachable over the network by anyone who knows the computer's address.",
    'статистика Streamlit не отключена':
        'Streamlit usage statistics are not disabled',
    'В .streamlit/config.toml: [browser] gatherUsageStats = false':
        'In .streamlit/config.toml: [browser] gatherUsageStats = false',
    'Запускайте MINT из папки {HERE} (run_mint.sh / run_mint.bat) — иначе Streamlit не увидит .streamlit/config.toml':
        'Start MINT from the folder {HERE} (run_mint.sh / run_mint.bat) — otherwise Streamlit does not see .streamlit/config.toml',
    'Пробный запуск страницы':
        'Test run of the page',
    'пропущено: в этой установке нет streamlit.testing':
        'skipped: this installation has no streamlit.testing',
    'страница не запустилась':
        'the page did not start',
    'страница открылась с ошибкой':
        'the page opened with an error',
    'страница открывается без ошибок ({v:.1f} с)':
        'the page opens without errors ({v:.1f} s)',
    '{titles}; вкладок: {n_tabs}':
        '{titles}; tabs: {n_tabs}',
    'Самопроверка установки MINT':
        'MINT installation self-check',
    'не отправлять тестовый запрос языковой модели':
        'do not send a test request to the language model',
    'не проверять разбор .docx':
        'do not check .docx parsing',
    'не открывать страницу MINT для проверки':
        'do not open the MINT page for checking',
    'Самопроверка MINT {MINT_VERSION} — {v}':
        'MINT self-check {MINT_VERSION} — {v}',
    '\nИтог: в порядке {ok}, предупреждений {warn}, ошибок {fail}.':
        '\nSummary: {ok} OK, {warn} warnings, {fail} errors.',
    'Исправьте ошибки по подсказкам выше. Если непонятно — перешлите этот вывод разработчику (ключей в нём нет).':
        'Fix the errors using the hints above. If anything is unclear, send this output to the developer (it contains no keys).',
    'Можно запускать: run_mint.sh (Linux) или run_mint.bat (Windows).':
        'Ready to start: run_mint.sh (Linux, macOS) or run_mint.bat (Windows).',
    # ---- added: values inside messages
    'не сообщается':
        'not reported',
    'нет (используются значения по умолчанию)':
        'none (default values are used)',
    '(первая из списка сервера)':
        '(the first one listed by the server)',
    'не подключён':
        'not connected',

    # ---- evaluation.py, eval_search.py
    'гибрид + реранкер {w}':
        'hybrid + reranker {w}',
    '{name} + multi-query':
        '{name} + multi-query',
    'только dense':
        'dense only',
    'только BM25':
        'BM25 only',
    'гибрид':
        'hybrid',
    '**{a}** против **{b}**: выше на {wins}, ниже на {losses} из {n} вопросов; {verdict}':
        '**{a}** vs **{b}**: higher on {wins}, lower on {losses} of {n} questions; {verdict}',
    'медиана {m:.2f} (мин {lo:.2f}, макс {hi:.2f})':
        'median {m:.2f} (min {lo:.2f}, max {hi:.2f})',
    '✓ сигнал':
        '✓ signal',
    '✗ без сигнала':
        '✗ no signal',
    'нет реранкера':
        'no reranker',
    'реранкер не ответил':
        'reranker did not respond',
    '# Оценка поиска MINT — {when}':
        '# MINT search evaluation — {when}',
    'Вопросов: {n} (с ответом в базе — {n_ans}, без ответа — {n_none}). Фрагментов в контексте модели (top_k): {top_k}. Модель эмбеддингов: {embed}; реранкер: {rr}.':
        'Questions: {n} (answer in the base — {n_ans}, no answer — {n_none}). Fragments in the model context (top_k): {top_k}. Embedding model: {embed}; reranker: {rr}.',
    '## Сравнение конфигураций':
        '## Configurations compared',
    'hit@N — правильный фрагмент среди первых N; hit@{top_k} — попал в контекст модели (top_k); MRR — средняя обратная позиция (1 — всегда первый). «Нет ответа распознан» — доля вопросов без ответа, по которым сработал сигнал «уверенность низкая»; «ложная тревога» — сигнал на вопросах, где ответ есть.':
        'hit@N — the right fragment is among the first N; hit@{top_k} — it reached the model context (top_k); MRR — mean reciprocal rank (1 — always first). “No answer detected” — share of no-answer questions where the “low confidence” signal fired; “false alarm” — the signal on questions that do have an answer.',
    '## Вопросы, где правильный фрагмент не попал в контекст ({name})':
        '## Questions where the right fragment missed the context ({name})',
    'В details.csv в колонках «Место» у вопросов без ответа — сработал ли сигнал: «✓ сигнал» или «✗ без сигнала»; «> {k}» — правильный фрагмент не найден среди первых {k}.':
        'In details.csv, the “Rank” columns of no-answer questions show whether the signal fired: “✓ signal” or “✗ no signal”; “> {k}” — the right fragment is not among the first {k}.',
    'Запросов к сервисам: эмбеддинги {e} (без ответа {ef}), реранкер {r} (с ошибкой {rf}).':
        'Service requests: embeddings {e} (no response {ef}), reranker {r} (failed {rf}).',
    'места правильного фрагмента совпали на всех вопросах.':
        'the right fragment had the same rank on every question.',
    '— (нет в базе)':
        '— (not in the base)',
    '{path}: вопросов не найдено.':
        '{path}: no questions found.',
    'База знаний пуста или не найдена ({kb_path}).':
        'The knowledge base is empty or not found ({kb_path}).',
    'Нет ответа распознан':
        'No answer detected',
    'Ложная тревога':
        'False alarm',
    '**Лучшая по MRR:** {best}.':
        '**Best by MRR:** {best}.',
    'Случайна ли разница — в разделе «Где конфигурации расходятся».':
        'Whether the difference is chance — see “Where configurations differ”.',
    'С реранкером «уверенность низкая» ставится, если лучший балл реранкера ниже порога `low_conf_rerank`.':
        'With a reranker, “low confidence” is set when the best reranker score is below `low_conf_rerank`.',
    'Реранкера нет: «уверенность низкая» ставится, если доля слов вопроса в контексте ниже порога `low_conf_lexical` и dense с BM25 не сошлись в топ-N.':
        'No reranker: “low confidence” is set when the share of question words in the context is below `low_conf_lexical` and dense and BM25 disagree in the top N.',
    '## Пороги сигнала «уверенность низкая» (для текущих настроек)':
        '## “Low confidence” thresholds (for the current settings)',
    'Доля слов вопроса в контексте: с ответом — {a}; без ответа — {b}.':
        'Share of question words in the context: with an answer — {a}; without — {b}.',
    'Таких нет.':
        'None.',
    '## Вопросы без ответа в базе ({name})':
        '## Questions with no answer in the base ({name})',
    'Сигнал «уверенность низкая» сработал на {caught} из {n}. Когда он срабатывает, модель получает предупреждение, что ответа в базе, вероятно, нет, и меньше домысливает.':
        'The “low confidence” signal fired on {caught} of {n}. When it fires, the model is warned that the base probably has no answer, and it makes things up less.',
    '⚠️ Для {n} вопросов эмбеддинг не получен — по ним работал только BM25.':
        '⚠️ No embedding for {n} question(s) — only BM25 worked for them.',
    'p = {p:.2f} — разница, скорее всего, не случайна.':
        'p = {p:.2f} — the difference is most likely not chance.',
    'p = {p:.2f} — разница может быть случайной; чтобы её подтвердить, нужно больше вопросов (40–60) или вопросы, на которых конфигурации расходятся.':
        'p = {p:.2f} — the difference may be chance; to confirm it, use more questions (40–60) or questions where the configurations differ.',
    'текст':
        'text',
    'черновик ({kind}) — проверьте':
        'draft ({kind}) — check it',
    '{path}: нет колонки question (вопрос). Найдены колонки: {cols}':
        '{path}: no question column. Columns found: {cols}',
    'Конфигурация':
        'Configuration',
    '⚠️ В прошлом прогоне было другое число вопросов с ответом ({prev}, сейчас {n_ans}): сравнение показательно, только если набор вопросов тот же.':
        '⚠️ The previous run had a different number of answerable questions ({prev}, now {n_ans}): the comparison is meaningful only for the same question set.',
    'Чтобы применить: в config.yaml `weight_rerank: {w}` (раздел search).':
        'To apply: `weight_rerank: {w}` in config.yaml (search section).',
    '## Где конфигурации расходятся':
        '## Where configurations differ',
    'Сравнение на одних и тех же вопросах: на скольких одна конфигурация ставит правильный фрагмент выше другой. p — вероятность получить такой перекос случайно, если конфигурации на самом деле равны (критерий знаков); вопросы, где места совпали, не учитываются.':
        'Compared on the same questions: on how many one configuration ranks the right fragment higher than the other. p — the chance of such a skew if the configurations are actually equal (sign test); questions with equal ranks are not counted.',
    'Лучший балл реранкера: на вопросах с ответом — {a}; без ответа — {b}.':
        'Best reranker score: on answerable questions — {a}; without an answer — {b}.',
    '★ — лучший баланс; текущий порог менять не нужно.':
        '★ — best balance; the current threshold needs no change.',
    '★ — лучший баланс. Чтобы применить: в config.yaml `{key}: {v}` (раздел confidence).':
        '★ — best balance. To apply: `{key}: {v}` in config.yaml (confidence section).',
    'Без реранкера сигнал слабее: слова вопроса часто есть в базе, даже когда ответа нет. Реранкер, даже с `weight_rerank: 0`, отличает такие вопросы заметно лучше.':
        'Without a reranker the signal is weaker: the question words are often in the base even when the answer is not. A reranker, even with `weight_rerank: 0`, tells such questions apart much better.',
    'Пороги «уверенность низкая» не подбирались: добавьте в набор 5–10 вопросов, ответа на которые в базе нет (колонка file пустая).':
        '“Low confidence” thresholds were not tuned: add 5–10 questions the base has no answer to (empty file column).',
    'Сигнал «уверенность низкая»':
        '“Low confidence” signal',
    'Лучший балл реранкера':
        'Best reranker score',
    'Доля слов вопроса в контексте':
        'Share of question words in the context',
    'dense и BM25 согласны':
        'dense and BM25 agree',
    'Найдено (текущие настройки), топ-3':
        'Found (current settings), top 3',
    ' ⬅ текущие настройки':
        ' ⬅ current settings',
    '{d:+.0f} п.п.':
        '{d:+.0f} pp',
    'Чтобы применить, не отключая реранкер: в config.yaml `weight_rerank: 0` (раздел search) — порядок станет как у гибрида, а баллы реранкера по-прежнему решают, ставить ли «уверенность низкая».':
        'To apply without switching the reranker off: `weight_rerank: 0` in config.yaml (search section) — the order becomes the hybrid one, and reranker scores still decide whether to set “low confidence”.',
    ' ⬅ сейчас':
        ' ⬅ now',
    'Вопрос':
        'Question',
    'Ожидалось':
        'Expected',
    'Место':
        'Rank',
    'Найдено первым':
        'Found first',
    'Сигнал':
        'Signal',
    'Доля слов вопроса':
        'Share of question words',
    '{path}, строка {i}: не JSON ({e}).':
        '{path}, line {i}: not JSON ({e}).',
    'Ещё {n} — в details.csv.':
        '{n} more — in details.csv.',
    'ничего не найдено':
        'nothing found',
    '; цитата подобрана по смыслу':
        '; quote matched by meaning',
    '; цитата не найдена — впишите фразу сами':
        '; no quote found — type the phrase yourself',
    '✗ нет':
        '✗ no',
    'Первым':
        'First',
    '# Черновик: проверьте каждый вопрос, перефразируйте как спросил бы пользователь, удалите неудачные; добавьте свои реальные вопросы и 5–10 вопросов без ответа в базе (file пустой).':
        '# Draft: check each question, reword it the way a user would ask, delete the weak ones; add your real questions and 5–10 questions with no answer in the base (empty file).',
    'Вопросов: {n}; конфигураций: {c}; top_k = {k}. База: {kb}':
        'Questions: {n}; configurations: {c}; top_k = {k}. Base: {kb}',
    'Записано вопросов: {n} (не удалось: {failed}; цитата подобрана по смыслу: {near}) → {out}':
        'Questions written: {n} (failed: {failed}; quote matched by meaning: {near}) → {out}',
    'Важно: вопросы, написанные моделью по тексту фрагмента, похожи на него по словам и завышают результат BM25. Перед оценкой перепишите их своими словами и добавьте реальные вопросы.':
        'Important: questions the model writes from a fragment share its wording and inflate BM25 results. Before the evaluation, reword them and add real questions.',
    '⚠️ Вопрос {n}: файла {miss} нет в базе — вопрос не сможет быть найден.':
        '⚠️ Question {n}: file {miss} is not in the base — the question cannot be found.',
    'Отчёт: {r}\nПо вопросам (Excel): {d}':
        'Report: {r}\nPer question (Excel): {d}',
    'Генерирую вопросы: {i}/{n}':
        'Generating questions: {i}/{n}',
    'Готово за {s:.0f} с':
        'Done in {s:.0f} s',
    '⚠️ Не удалось прочитать {path}: {e}':
        '⚠️ Could not read {path}: {e}',
    'ОШИБКА':
        'ERROR',
    'Внимание':
        'Warning',
    # ---- ui/quality.py, evaluation.py (проверка качества)
    '— ответа в базе нет —':
        '— not in the base —',
    '## Ответы чата (текущие настройки)':
        '## Chat answers (current settings)',
    'Ответ чата':
        'Chat answer',
    'Ссылка на ожидаемый документ':
        'Cites the expected document',
    'Ссылки мимо найденного':
        'References outside the fragments found',
    'не выбран документ':
        'no document chosen',
    'документа нет в базе':
        'the document is not in the base',
    'фраза не найдена в документе — перепишите её дословно или очистите':
        'the phrase is not in the document — copy it verbatim or clear it',
    'раздел не найден в документе':
        'the section is not in the document',
    'фраза и раздел не встречаются в одном фрагменте':
        'the phrase and the section never occur in one fragment',
    'Текущие настройки: {name}. Вопросов с ответом в базе — {a}, без ответа — {b}.':
        'Current settings: {name}. Questions with an answer in the base — {a}, without — {b}.',
    'Вся полоса — правильный фрагмент попал в контекст модели (hit@{k}), тёмная часть — он был первым (hit@1).':
        'The whole bar — the right fragment reached the model context (hit@{k}); the dark part — it came first (hit@1).',
    '🧪 Проверка качества':
        '🧪 Quality check',
    'Вопросы по документам базы, прогон поиска в нескольких настройках, рекомендации — без CSV и командной строки.':
        'Questions from the documents in the base, a search run with several settings, recommendations — no CSV, no command line.',
    'Открыть проверку качества':
        'Open the quality check',
    'Вопросы':
        'Questions',
    'Настройка':
        'Setup',
    'Составлено вопросов: {made} из {asked} — в базе больше нет фрагментов, по которым можно задать вопрос (нужно от 300 символов текста).':
        'Questions written: {made} of {asked} — the base has no more fragments to ask about (at least 300 characters of text are needed).',
    'Результаты':
        'Results',
    'MINT составит вопросы по документам базы, вы их проверите и дополните, затем каждый вопрос пройдёт через поиск в нескольких настройках. В итоге видно, на каком месте оказывается нужный фрагмент, какие настройки лучше и на каких вопросах поиск ошибается.':
        'MINT writes questions from the documents in the base, you check and add to them, then every question goes through search with several settings. You see where the right fragment ends up, which settings work better and which questions search gets wrong.',
    'Документов в базе: {d}. Вызовов модели: {n} — по одному на вопрос.':
        'Documents in the base: {d}. Model calls: {n} — one per question.',
    'Повторные запросы к эмбеддингам и реранкеру в разных настройках не отправляются.':
        'Repeated embedding and reranker requests across settings are not sent again.',
    '✨ Составить вопросы':
        '✨ Write questions',
    '✍️ Написать вопросы самому':
        '✍️ Write my own questions',
    '**Проверьте вопросы.** Перепишите вопрос так, как спросил бы сотрудник: модель берёт слова из фрагмента, и такие вопросы завышают результат поиска по словам. Снимите галочку с неудачных, добавьте свои строки внизу таблицы.':
        '**Check the questions.** Reword each one the way an employee would ask: the model borrows words from the fragment, and such questions inflate keyword search results. Untick the weak ones, add your own rows at the bottom of the table.',
    'Прогон: {compare}{answers}{multi}. Изменить — «← Назад».':
        'Run: {compare}{answers}{multi}. To change it — “← Back”.',
    '▶ Запустить проверку ({n})':
        '▶ Run the check ({n})',
    '✨ Ещё {n} вопросов':
        '✨ {n} more questions',
    '← Назад':
        '← Back',
    '✏️ Изменить вопросы и проверить снова':
        '✏️ Edit the questions and check again',
    '🔄 Новая проверка':
        '🔄 New check',
    '✕ Закрыть':
        '✕ Close',
    'Порог «уверенность низкая»: балл реранкера':
        '“Low confidence” threshold: reranker score',
    'Порог «уверенность низкая»: доля слов вопроса':
        '“Low confidence” threshold: share of question words',
    'Применить в этой сессии':
        'Apply to this session',
    '✓ Применено в этой сессии':
        '✓ Applied to this session',
    'все':
        'all',
    'не попали в контекст':
        'missed the context',
    'без ответа в базе':
        'not in the base',
    'Показать':
        'Show',
    '🧪 Проверка качества поиска':
        '🧪 Search quality check',
    'со ссылками мимо найденного':
        'with references outside the fragments found',
    'Сколько вопросов составить':
        'How many questions to write',
    'Сравнить настройки поиска':
        'Compare search settings',
    'Проверить и ответы чата':
        'Check chat answers too',
    '↺ Вопросы прошлой проверки ({when})':
        '↺ Questions from the last check ({when})',
    'Документ с ответом':
        'Document with the answer',
    'Раздел':
        'Section',
    'Ответ в документе — дословная фраза':
        'Answer in the document — verbatim phrase',
    'Примечание':
        'Note',
    'Не удалось составить вопросов: {n} — модель ответила не в том формате.':
        'Questions that could not be written: {n} — the model replied in the wrong format.',
    'Нет вопросов, ответа на которые в базе нет: порог «уверенность низкая» подобрать не получится. Добавьте 5–10 вопросов о том, чего в документах точно нет.':
        'There are no questions the base cannot answer, so the “low confidence” threshold cannot be tuned. Add 5–10 questions about things the documents certainly do not cover.',
    '⬇ Вопросы (.csv)':
        '⬇ Questions (.csv)',
    'Готовлю прогон…':
        'Preparing the run…',
    'Применено к текущей сессии: {v}':
        'Applied to the current session: {v}',
    'Прошлая проверка ({when}) была на другом наборе вопросов — изменения не показаны.':
        'The last check ({when}) used a different question set — changes are not shown.',
    'Текущие настройки — лучшие из проверенных; менять ничего не нужно.':
        'The current settings are the best of those checked; nothing needs changing.',
    'Чтобы закрепить — в config.yaml:':
        'To keep it — in config.yaml:',
    'Пороги сигнала «уверенность низкая»':
        '“Low confidence” thresholds',
    'Таких вопросов нет.':
        'No such questions.',
    '⬇ Отчёт (.md)':
        '⬇ Report (.md)',
    '⬇ По вопросам (.csv)':
        '⬇ Per question (.csv)',
    'Отчёт сохранён: {path}':
        'Report saved: {path}',
    'База знаний пуста: проверять нечего. Добавьте документы на боковой панели («Добавить регламенты в базу»).':
        'The knowledge base is empty: nothing to check. Add documents in the sidebar (“Add reference documents to the base”).',
    'Шаги проверки':
        'Check steps',
    'п.п.':
        'pp',
    'в контексте модели':
        'in the model context',
    'первым':
        'first',
    'Итоги проверки':
        'Check results',
    'Настройки':
        'Settings',
    'ссылка на нужный документ':
        'cites the expected document',
    'Один вызов модели на вопрос. Фрагменты берутся поровну из каждого документа.':
        'One model call per question. Fragments are taken evenly from every document.',
    'Кроме текущих настроек — только векторный поиск, только BM25, гибрид и разные веса реранкера. Без сравнения быстрее: текущие настройки, векторный поиск и гибрид.':
        'Besides the current settings — vector search only, BM25 only, hybrid and several reranker weights. Without the comparison it is faster: current settings, vector search and hybrid.',
    'Добавить вариант с multi-query':
        'Add a multi-query variant',
    'Составляю вопросы…':
        'Writing questions…',
    'Снимите галочку, чтобы не включать вопрос в проверку':
        'Untick to leave the question out of the check',
    'Как спросил бы сотрудник':
        'The way an employee would ask',
    'Где ответ. «{na}» — для вопросов, ответа на которые в базе нет: по ним проверяется сигнал «уверенность низкая».':
        'Where the answer is. “{na}” — for questions the base cannot answer: they test the “low confidence” signal.',
    'Часть названия раздела — необязательно':
        'Part of the section title — optional',
    'Короткая фраза из нужного фрагмента: по ней понятно, что поиск нашёл именно его. Необязательно, но точнее всего.':
        'A short phrase from the right fragment: it shows that search found exactly that one. Optional, but the most precise.',
    'Что поправить ({n})':
        'To fix ({n})',
    'Фрагмент, по которому составлен вопрос':
        'Fragment the question was written from',
    '⬇ Документ целиком ({name})':
        '⬇ The whole document ({name})',
    '{stage}: {done} из {total}':
        '{stage}: {done} of {total}',
    '▲▼ — изменение с прошлой проверки ({when}).':
        '▲▼ — change since the last check ({when}).',
    'Что поменять':
        'What to change',
    'Разница в поиске может быть случайной (p = {p:.2f}): прежде чем менять config.yaml, проверьте на большем наборе вопросов.':
        'The search difference may be chance (p = {p:.2f}): check with a larger question set before changing config.yaml.',
    'По вопросам':
        'Per question',
    '⬇ Ответы чата (.csv)':
        '⬇ Chat answers (.csv)',
    'Отчёт не сохранён на диск ({e}) — скачайте его кнопками выше.':
        'The report was not saved to disk ({e}) — download it with the buttons above.',
    'без изменений':
        'no change',
    'Ещё одна настройка: поиск по нескольким формулировкам вопроса (+1 вызов модели на вопрос).':
        'One more setting: search with several wordings of the question (+1 model call per question).',
    'Составляю вопросы: {i} из {n}':
        'Writing questions: {i} of {n}',
    'сравнение настроек поиска':
        'search settings compared',
    'только текущие настройки, векторный поиск и гибрид':
        'current settings, vector search and hybrid only',
    '; ответы чата':
        '; chat answers',
    '; вариант с multi-query':
        '; multi-query variant',
    'в проверке':
        'in the check',
    'с ответом':
        'with an answer',
    'поправить':
        'to fix',
    'Ответы чата':
        'Chat answers',
    'сейчас':
        'now',
    '1 — всегда первым':
        '1 — always first',
    'ложные тревоги':
        'false alarms',
    'нет ответа распознан':
        'no answer detected',
    'лучшая по MRR':
        'best by MRR',
    '«{q}» — не выбран документ: выберите файл или «{na}»; пока строка не входит в проверку':
        '“{q}” — no document chosen: pick a file or “{na}”; until then the row is left out',
    '«{q}» — {why}':
        '“{q}” — {why}',
    # ---- проверка ответов чата (mint/evaluation.py, mint/ui/quality.py)
    'сбой модели или шлюза':
        'a model or gateway failure',
    'поиск: нужного фрагмента нет в контексте':
        'search: the right fragment is not in the context',
    'модель: «информации нет», хотя фрагмент в контексте':
        'model: “no information”, although the fragment is in the context',
    'модель: нет ссылки на нужный документ':
        'model: no reference to the right document',
    'модель: ссылки мимо найденных фрагментов':
        'model: references outside the fragments found',
    'модель ответила, хотя ответа в базе нет':
        'model answered, although the base has no answer',
    'версия промптов':
        'prompt version',
    'язык':
        'language',
    'модель':
        'model',
    'температура':
        'temperature',
    'повторов':
        'repeats',
    'На общих вопросах ответы лучше на {b}, хуже на {w}, без изменений — {s}; {tail}':
        'On the shared questions answers are better on {b}, worse on {w}, unchanged on {s}; {tail}',
    'разницы нет.':
        'no difference.',
    'Каждый вопрос задан чату с текущими настройками{rep}; ответы проверены без модели: ссылки сверены с найденными фрагментами, «информации нет» — по фразе chat_no_info из промпта. Промпты: **{v}**.':
        'Every question was asked in chat with the current settings{rep}; the answers were checked without a model: references against the fragments found, “no information” by the chat_no_info phrase of the prompt. Prompts: **{v}**.',
    'верный ответ':
        'right answer',
    'ложное «информации нет»':
        'false “no information”',
    'честное «информации нет»':
        'honest “no information”',
    'p = {p:.2f} — разница может быть случайной; нужно больше вопросов или повторов.':
        'p = {p:.2f} — the difference may be chance; more questions or repeats are needed.',
    '- Нужный фрагмент был в контексте модели: {v}.':
        '- The right fragment was in the model context: {v}.',
    '- ⚠️ Модель не ответила {n} раз — эти ответы не учтены.':
        '- ⚠️ The model did not answer {n} times — those answers are not counted.',
    '### Где ошибки: поиск или модель':
        '### Where the errors are: search or model',
    '«Поиск» — правьте настройки поиска (сравнение настроек выше); «модель» — промпт чата (страница «📝 Промпты» → «Системный промпт чата») или модель.':
        '“Search” — tune the search settings (the comparison above); “model” — the chat prompt (the “📝 Prompts” page → “Chat system prompt”) or the model.',
    '### Сравнение ответов с прошлой проверкой':
        '### Answers compared with the previous check',
    'Изменилось: {what}.':
        'Changed: {what}.',
    '### Ответы с ошибками':
        '### Answers with errors',
    'Повтор':
        'Repeat',
    'Итог':
        'Result',
    'Причина':
        'Reason',
    '«Информации нет»':
        '“No information”',
    'Фрагмент в контексте':
        'Fragment in the context',
    'Фраза в ответе':
        'Phrase in the answer',
    'Время, с':
        'Time, s',
    'Источники':
        'Sources',
    '⚠️ Изменилось больше одного параметра — разницу нельзя приписать чему-то одному.':
        '⚠️ More than one parameter changed — the difference cannot be attributed to any one of them.',
    ' (повтор {i})':
        ' (repeat {i})',
    '- ожидалось: {e}; причина: {why}':
        '- expected: {e}; reason: {why}',
    '- ответ: {a}':
        '- answer: {a}',
    'Ещё {n} — в answers.csv.':
        '{n} more — in answers.csv.',
    ', повторов: {n}':
        ', repeats: {n}',
    'Ответов':
        'Answers',
    'ничего из настроек':
        'none of the settings',
    'Изменение':
        'Change',
    'Было':
        'Before',
    'Стало':
        'After',
    'лучше':
        'better',
    'хуже':
        'worse',
    '{ok} из {n} ✓':
        '{ok} of {n} ✓',
    'Документов в базе: {d}. Вызовов модели: {n} — по одному на вопрос и на каждый ответ чата.':
        'Documents in the base: {d}. Model calls: {n} — one per question and one per chat answer.',
    'ответы с ошибками':
        'answers with errors',
    'Промпты: {v} · язык: {language} · модель: {m}':
        'Prompts: {v} · language: {language} · model: {m}',
    'Модель не ответила {n} раз — эти ответы не учтены.':
        'The model did not answer {n} times — those answers are not counted.',
    '«Поиск» — нужного фрагмента не было в контексте: правьте настройки поиска. «Модель» — фрагмент был, а ответ не тот: правьте промпт чата или модель.':
        '“Search” — the right fragment was not in the context: tune the search settings. “Model” — the fragment was there but the answer is wrong: change the chat prompt or the model.',
    '**С прошлой проверкой ответов** (изменилось: {what}). {verdict}':
        '**Compared with the previous answer check** (changed: {what}). {verdict}',
    'Это первая проверка ответов: следующая (например, после правки промпта) сравнится с ней.':
        'This is the first answer check: the next one (for example, after a prompt change) will be compared with it.',
    'Ответ: итог':
        'Answer: result',
    'Каждый вопрос задаётся чату с текущими настройками (+1 вызов модели на вопрос): есть ли ссылка на нужный документ, нет ли ссылок мимо найденного, честное ли «информации нет», если ответа в базе нет; ошибка — поиска или модели. Нужно после правки промптов: результат сравнивается с прошлой проверкой по версии промптов.':
        'Every question is also asked in chat with the current settings (+1 model call per question): does the answer cite the right document, are there references outside the fragments found, is “no information” honest when the base has no answer; is an error in search or in the model. Use it after changing prompts: the result is compared with the previous check by prompt version.',
    'Сколько раз задать чату каждый вопрос':
        'How many times to ask each question in chat',
    'Модель отвечает не всегда одинаково. Чтобы сравнить промпты до и после правки, задайте каждый вопрос 2–3 раза: случайные расхождения сгладятся.':
        'The model does not always answer the same way. To compare prompts before and after a change, ask each question 2–3 times: random differences even out.',
    'повторов каждого вопроса: {n}':
        'repeats of each question: {n}',
    '**Где ошибки:** поиск — {s}, модель — {m}.':
        '**Where the errors are:** search — {s}, model — {m}.',
    ' ×{n}':
        ' ×{n}',
    # ---- страница «📝 Промпты» и свои правки промптов
    'Чат':
        'Chat',
    'Системный промпт чата':
        'Chat system prompt',
    'Роль и правила ответа в чате. Ссылки — в формате [Источник: файл, раздел]: по нему MINT проверяет, что ссылка ведёт на найденный фрагмент.':
        'Role and answer rules for the chat. Citations use the format [Source: file, section]: MINT uses it to check that a citation points to a retrieved fragment.',
    'Фраза «информации нет»':
        '“No information” phrase',
    'Что модель отвечает, если в документах ответа нет. Подставляется в системный промпт; по ней проверка качества узнаёт честное «информации нет».':
        'What the model answers when the documents have no answer. It is inserted into the system prompt; the quality check uses it to recognise an honest “no information”.',
    'Пометка «уверенность низкая»':
        '“Low confidence” note',
    'Добавляется в начало контекста, когда поиск не уверен в найденном. Системный промпт чата ссылается на неё — меняйте их вместе.':
        'Added at the start of the context when search is not confident in what it found. The chat system prompt refers to it — change them together.',
    'Уточнение вопроса по истории':
        'Follow-up question rewrite',
    'Переписывает уточняющий вопрос («а для второго контура?») в самостоятельный — для поиска.':
        'Rewrites a follow-up question (“and for the second circuit?”) into a standalone one — for search.',
    'Перефразировка вопроса (multi-query)':
        'Question paraphrase (multi-query)',
    'Вторая формулировка вопроса для поиска, если включён multi-query.':
        'A second wording of the question for search, when multi-query is on.',
    'Аудит документа':
        'Document review',
    'Проверка раздела':
        'Section review',
    'Роль и правила проверки одного раздела. Теги критичности и фраза «раздел чистый» обязательны: по ним MINT разбирает замечания.':
        'Role and rules for reviewing one section. The severity tags and the “section is clean” phrase are required: MINT parses the remarks by them.',
    'Критерии по умолчанию':
        'Default criteria',
    'Текст поля «Общие критерии проверки» во вкладке «Аудит документа». У каждого профиля (боковая панель → «🧭 Профиль») — свои критерии.':
        'Text of the “General review criteria” field on the “Document review” tab. Each profile (sidebar → “🧭 Profile”) has its own criteria.',
    'Универсальный — любые документы':
        'General — any documents',
    'Архитектура и ИТ-решения':
        'Architecture and IT solutions',
    'Неизвестный профиль profile = «{v}» — используется «{d}». Профили: {names}.':
        'Unknown profile profile = “{v}” — “{d}” is used. Profiles: {names}.',
    'Docling не открыл файл как документ Word (.docx): файл повреждён или это другой формат с расширением .docx.':
        'Docling could not open the file as a Word document (.docx): the file is damaged or it is another format with the .docx extension.',
    'Пакеты не те, что проверены для MINT (например, другая версия Docling). Переустановите их по requirements.lock: ./install.sh --clean (Windows: install.bat --clean).':
        'The packages are not the ones tested for MINT (for example, another Docling version). Reinstall them from requirements.lock: ./install.sh --clean (Windows: install.bat --clean).',
    'вкладок: {n_tabs}':
        'tabs: {n_tabs}',
    '🧭 Профиль:':
        '🧭 Profile:',
    'Набор промптов для чата, аудита и контроля исправлений. «Архитектура и ИТ-решения» — для проектной документации: роли архитектурного комитета и архитектурные критерии аудита. «Универсальный» — для любых документов: договоров, положений, отчётов, инструкций. Профиль по умолчанию — profile в config.yaml (не задан — архитектурный); тексты профиля — на странице «📝 Промпты».':
        'The prompt set for chat, document review and verification of fixes. “Architecture and IT solutions” — for design documentation: architecture board roles and architecture review criteria. “General” — for any documents: contracts, policies, reports, manuals. The default profile is profile in config.yaml (not set — architecture); the profile texts are on the “📝 Prompts” page.',
    'Критерии, если поле пустое':
        'Criteria when the field is empty',
    'Используются, когда поле критериев очищено.':
        'Used when the criteria field has been cleared.',
    'Правило «особого внимания»':
        '“Special attention” rule',
    'Добавляется к правилам проверки, если заполнено поле «Особое внимание».':
        'Added to the review rules when the “Special attention” field is filled in.',
    'Нормы из базы':
        'Norms from the base',
    'Заголовок блока с нормативными фрагментами, найденными для раздела.':
        'Heading of the block with the normative fragments found for the section.',
    'Нормы не найдены':
        'No norms found',
    'Пометка, если для раздела в базе ничего не нашлось.':
        'Note used when nothing was found in the base for the section.',
    'Аудит без базы знаний':
        'Review without a knowledge base',
    'Пометка, если аудит идёт без нормативной базы.':
        'Note used when the review runs without a normative base.',
    'Второй проход: оставить или удалить каждое замечание, критичность и дословная цитата. JSON-поля и коды вердиктов и критичности обязательны.':
        'Second pass: keep or drop each finding, its severity and verbatim quote. The JSON fields and the verdict and severity codes are required.',
    'Контроль исправлений':
        'Verification of fixes',
    'Проверка замечания':
        'Remark check',
    'Исправлено ли замечание в новой редакции. JSON-ответ со статусом и цитатой обязателен.':
        'Whether a remark is fixed in the new version. A JSON answer with a status and a quote is required.',
    'Проверка качества':
        'Quality check',
    'Черновик вопросов по базе':
        'Draft questions from the base',
    'По фрагменту базы — вопрос и дословная цитата с ответом. JSON-ответ обязателен.':
        'From a base fragment — a question and a verbatim quote with the answer. A JSON answer is required.',
    '«{key}» — разметка, её не правят':
        '“{key}” is markup — it is not edited',
    'промпта «{key}» нет':
        'there is no prompt “{key}”',
    'текст пустой':
        'the text is empty',
    'нет подстановки: {v} — её заполняет MINT':
        'placeholder missing: {v} — MINT fills it in',
    'неизвестная подстановка: {v} — MINT её не заполнит':
        'unknown placeholder: {v} — MINT will not fill it in',
    'нет обязательной части формата ответа: {v} — по ней MINT разбирает ответ модели':
        "required part of the answer format missing: {v} — MINT parses the model's answer by it",
    '{name} не прочитан ({e}) — действуют промпты по умолчанию.':
        '{name} could not be read ({e}) — the default prompts are used.',
    '{name}: ожидаются разделы ru: и en: — файл пропущен.':
        '{name}: sections ru: and en: are expected — the file is skipped.',
    '{name}: раздел «{language}» пропущен — нужны ru: или en:.':
        '{name}: section “{language}” skipped — ru: or en: is expected.',
    '{language}.{key}: нет текста — пропущено.':
        '{language}.{key}: no text — skipped.',
    '{language}.{key} не применён: {why}.':
        '{language}.{key} not applied: {why}.',
    '✎ сохранено':
        '✎ saved',
    '✎ в сеансе':
        '✎ in session',
    '📝 Промпты':
        '📝 Prompts',
    'Свои правки: {n}.':
        'Your edits: {n}.',
    'Действуют тексты по умолчанию.':
        'The default texts are in effect.',
    'Тексты для модели: правка, проверка на вопросах, возврат к умолчанию.':
        'Texts for the model: edit, check on questions, return to default.',
    'Открыть промпты':
        'Open prompts',
    'по умолчанию':
        'default',
    'Язык: {language} — тексты на другом языке правятся при другом языке интерфейса. Профиль: {profile} — умолчания этого профиля (сменить — боковая панель → «🧭 Профиль»). Версия набора: {v}. Свои правки сохраняются в {path}{exists}; они действуют во всех профилях.':
        'Language: {language} — texts in the other language are edited with the other interface language. Profile: {profile} — the defaults of this profile (to change it: sidebar → “🧭 Profile”). Prompt set version: {v}. Your edits are saved to {path}{exists}; they apply in every profile.',
    ' (пока нет)':
        ' (not yet created)',
    'Промпт':
        'Prompt',
    'Текст по умолчанию изменился после того, как вы сохранили свою правку (обновление MINT). Сравните их ниже и перенесите нужное в свою правку — или верните умолчание.':
        'The default text has changed since you saved your edit (MINT update). Compare them below and carry over what you need into your edit — or return to the default.',
    '**Обязательно в тексте** — без этого правка не применится:':
        '**Required in the text** — without it the edit will not be applied:',
    '- подстановки (их заполняет MINT): {v}':
        '- placeholders (MINT fills them in): {v}',
    '- формат ответа (его разбирает MINT): {v}':
        '- answer format (MINT parses it): {v}',
    'Текст':
        'Text',
    'Попробовать в сеансе':
        'Try in this session',
    'Правка действует только в этом окне браузера: чат, аудит и проверка качества идут с ней. Другие пользователи и после перезапуска — по-прежнему.':
        'The edit applies only in this browser window: chat, review and the quality check use it. Other users, and everyone after a restart, keep the previous text.',
    'Сохранить':
        'Save',
    'Записать в {name}: правка действует для всех и после перезапуска.':
        'Write to {name}: the edit applies to everyone and survives a restart.',
    'Вернуть умолчание':
        'Return to default',
    'Убрать свою правку из сеанса и из {name}.':
        'Remove your edit from the session and from {name}.',
    'Проверить правку':
        'Check the edit',
    'Применить правку в сеансе и открыть «Проверку качества» с ответами чата на вопросах прошлой проверки: результат сравнится с прошлой проверкой ответов.':
        'Apply the edit in the session and open the “Quality check” with chat answers on the questions of the previous check: the result will be compared with the previous answer check.',
    'Аудит, контроль исправлений и черновик вопросов проверкой ответов чата не измеряются — проверьте правку на документе с известными замечаниями.':
        'Review, verification of fixes and draft questions are not measured by the chat answer check — test the edit on a document with known remarks.',
    'Перефразировка работает, только если включён multi-query (Экспертные настройки → Поиск и контекст).':
        'The paraphrase works only when multi-query is on (Expert settings → Search and context).',
    'Правка действует в этом сеансе. Версия промптов: {v}':
        'The edit is in effect in this session. Prompt version: {v}',
    'Не сохранено: {e}':
        'Not saved: {e}',
    'Сохранено в {path}. Версия промптов: {v}':
        'Saved to {path}. Prompt version: {v}',
    'Не удалось изменить {path}: {e}':
        'Could not change {path}: {e}',
    'Действует текст по умолчанию.':
        'The default text is in effect.',
    'Прошлой проверки нет: составьте вопросы — ответы чата будут проверены, а следующая проверка после правки сравнится с этой.':
        'There is no previous check: compose questions — the chat answers will be checked, and the next check after an edit will be compared with this one.',
    'Разница с текстом по умолчанию':
        'Difference from the default text',
    '(разница только в пробелах)':
        '(the difference is only in whitespace)',
    'Разметка — не правится ({n})':
        'Markup — not editable ({n})',
    'Заголовки контекста, вопроса и источников, которые MINT собирает сам: их разбирает код (например, проверка ссылок ищет «=== ИСТОЧНИК: … ===»).':
        'Context, question and source headers that MINT builds itself: the code parses them (for example, the citation check looks for “=== SOURCE: … ===”).',
    '{name} не прочитан — исправьте или удалите файл и сохраните снова ({e}).':
        '{name} could not be read — fix or delete the file and save again ({e}).',
    'в сеансе':
        'in session',
    'сохранено':
        'saved',
    'Свои правки промптов: {v}.':
        'Your prompt edits: {v}.',
    'свои правки: {v}':
        'your edits: {v}',
    # ---- форматы: .pdf без моделей, .md, .txt
    '❌ В документе не найден текст.':
        '❌ No text found in the document.',
    'Заголовков: {n}.':
        'Headings: {n}.',
    'стили заголовков Word':
        'Word heading styles',
    'закладки PDF':
        'PDF bookmarks',
    'страница «Содержание»':
        'the “Contents” page',
    'заголовки слайдов':
        'slide titles',
    'размер и жирность шрифта (приблизительно)':
        'font size and weight (approximate)',
    'заголовки Markdown':
        'Markdown headings',
    'нумерованные строки':
        'numbered lines',
    'заголовков нет':
        'no headings',
    'Текст в PDF повреждён: шрифты сохранены без кодировки, вместо букв — другие знаки. Так бывает после «Печати в PDF». Сохраните документ из Word через «Сохранить как PDF» или загрузите .docx.':
        'The text in the PDF is damaged: the fonts were saved without an encoding, so other characters stand in for the letters. This happens after “Print to PDF”. Save the document from Word with “Save as PDF” or upload the .docx.',
    'Структура: {how}.':
        'Structure: {how}.',
    'В PDF нет текстового слоя (скан или картинки): без распознавания текста MINT его не прочитает. Нужен исходный документ (.docx) или PDF, сохранённый из Word.':
        'The PDF has no text layer (a scan or images): without text recognition MINT cannot read it. Use the source document (.docx) or a PDF saved from Word.',
    'Формат файла «{name}» не поддерживается: подходят .docx, .pdf, .md и .txt.':
        'The format of “{name}” is not supported: use .docx, .pdf, .md or .txt.',
    '⚠️ Страниц без текста: {n} из {total} (картинки или сканы) — их содержимое в базу не попало.':
        '⚠️ Pages without text: {n} of {total} (images or scans) — their content is not in the base.',
    'Для .pdf нужен пакет pdfplumber: pip install pdfplumber':
        '.pdf needs the pdfplumber package: pip install pdfplumber',
    'Загрузить документы в общую Wiki (.docx, .pdf, .md, .txt)':
        'Upload documents to the shared Wiki (.docx, .pdf, .md, .txt)',
    'Документ разбирается (.docx — Docling; .pdf — по текстовому слою, без моделей: заголовки из закладок, оглавления или по шрифту), нарезается на фрагменты по рассчитанным параметрам и добавляется в базу. Сканы без текстового слоя не читаются. Повторная загрузка файла с тем же именем заменяет прежнюю версию. Оригинал сохраняется для переиндексации.':
        'The document is parsed (.docx — Docling; .pdf — from its text layer, without models: headings from bookmarks, the contents page or font size), chunked with the derived parameters and added to the base. Scans without a text layer cannot be read. Uploading a file with the same name replaces the previous version. The original is kept for re-indexing.',
    'Загрузить документ на согласование (.docx, .pdf, .md, .txt)':
        'Upload a document for approval (.docx, .pdf, .md, .txt)',
    'Документ преобразуется в Markdown и режется на разделы. Замечания примечаниями Word ставятся только в .docx; для других форматов — заключение и лог проверки.':
        'The document is converted to Markdown and split into sections. Findings are added as Word comments only to a .docx; other formats get the report and the review log.',
    '🔍 Разбор документа...':
        '🔍 Parsing the document...',
    '🔍 Как прочитан документ (.md)':
        '🔍 How the document was read (.md)',
    'Примечания в документ ставятся только для .docx — для этого формата есть заключение и лог проверки.':
        'Comments are added to the document only for .docx — for this format there are the report and the review log.',
    'Загрузить новую редакцию документа (.docx, .pdf, .md, .txt)':
        'Upload the new revision of the document (.docx, .pdf, .md, .txt)',
    'разбор .pdf (без моделей)':
        'reading .pdf (without models)',
    'torch {version} установлен — его тянет Docling, MINT он не нужен: .docx и .pdf разбираются без моделей':
        'torch {version} is installed — Docling pulls it in, MINT does not need it: .docx and .pdf are parsed without models',
    'torch не установлен — MINT он не нужен':
        'torch is not installed — MINT does not need it',
    # ---- таймауты аудита, рассуждения модели, свои параметры запроса
    '{s} с':
        '{s} s',
    'проверен с {n}-й попытки':
        'checked on attempt {n}',
    'Рассуждения модели':
        'Model reasoning',
    'Таймаут ответа LLM, с':
        'LLM response timeout, s',
    'выключены':
        'turned off',
    'как настроено на сервере':
        'as configured on the server',
    'llm_extra_body / LLM_EXTRA_BODY должен быть объектом JSON — параметры не отправляются.':
        'llm_extra_body / LLM_EXTRA_BODY must be a JSON object — the parameters are not sent.',
    'llm_extra_body: поля {v} задаёт сам MINT — они не отправляются.':
        'llm_extra_body: MINT sets the fields {v} itself — they are not sent.',
    'llm_extra_body / LLM_EXTRA_BODY — не JSON ({e}): параметры не отправляются.':
        'llm_extra_body / LLM_EXTRA_BODY is not JSON ({e}): the parameters are not sent.',
    '❌ [ТАЙМАУТ MINT]: модель не ответила за {llm_timeout} с. Увеличьте «Таймаут ответа LLM» в «Экспертных настройках» (раздел «Языковая модель»).':
        '❌ [MINT TIMEOUT]: the model did not answer within {llm_timeout} s. Increase “LLM response timeout” in “Expert settings” (the “Language model” section).',
    'Модель рассуждает перед ответом — включите там же «Выключить рассуждения модели».':
        'The model reasons before answering — turn on “Turn off model reasoning” there as well.',
    'Если модель рассуждает перед ответом — включите там же «Выключить рассуждения модели».':
        'If the model reasons before answering, turn on “Turn off model reasoning” there as well.',
    'Проверьте свои параметры запроса (llm_extra_body / LLM_EXTRA_BODY).':
        'Check your own request parameters (llm_extra_body / LLM_EXTRA_BODY).',
    'Выключить рассуждения модели':
        'Turn off model reasoning',
    'Модели с рассуждениями перед ответом «думают»: это тысячи токенов и десятки секунд на каждый запрос. Для ответов по документам и аудита рассуждения обычно не нужны. MINT передаёт шлюзу стандартный параметр выключения (vLLM, SGLang); шлюз, который его не знает, получает запрос без него. Для других шлюзов — свои параметры в llm_extra_body (config.yaml) или LLM_EXTRA_BODY (.env).':
        'Reasoning models “think” before answering: thousands of tokens and tens of seconds per request. Answers from documents and the review usually do not need it. MINT sends the gateway the standard switch-off parameter (vLLM, SGLang); a gateway that does not know it gets the request without it. For other gateways — your own parameters in llm_extra_body (config.yaml) or LLM_EXTRA_BODY (.env).',
    '💭 Модель рассуждает перед ответом — это медленнее. Выключить: «Экспертные настройки» → «Языковая модель» → «Выключить рассуждения модели».':
        '💭 The model reasons before answering — this is slower. To turn it off: “Expert settings” → “Language model” → “Turn off model reasoning”.',
    '🔁 Перепроверить непроверенные разделы ({n})':
        '🔁 Recheck unchecked sections ({n})',
    'Ещё раз проверить только те разделы, на которых модель не ответила, с таймаутом {t} с. Новые замечания добавятся к заключению; уже проверенные разделы не повторяются.':
        'Check again only the sections the model did not answer, with a {t} s timeout. New findings are added to the report; sections already checked are not repeated.',
    'Перепроверка непроверенных разделов...':
        'Rechecking unchecked sections...',
    '🔁 Разделов: {n}, таймаут {t} с.':
        '🔁 Sections: {n}, timeout {t} s.',
    '🔁 Не проверено разделов: {n} — проверяю их ещё раз с таймаутом {t} с.':
        '🔁 Sections not checked: {n} — checking them again with a {t} s timeout.',
    'целиком ({n} симв.)':
        'whole ({n} chars)',
    'оглавление — документ целиком не помещается в окно модели или выключен в настройках':
        "outline — the whole document does not fit into the model's context window or is turned off in the settings",
    'документ — одна часть':
        'the document is a single part',
    'Выключено в настройках.':
        'Turned off in the settings.',
    '## 🎯 ОТВЕТЫ НА ПУНКТЫ ОСОБОГО ВНИМАНИЯ':
        '## 🎯 ANSWERS TO THE SPECIAL ATTENTION POINTS',
    '## ❓ НЕ ПОДТВЕРЖДЕНО ИСТОЧНИКОМ — ПРОВЕРЬТЕ':
        '## ❓ NOT CONFIRMED BY A SOURCE — PLEASE CHECK',
    'Ссылки и цифры из этих замечаний не найдены ни в документе, ни в нормативных фрагментах, которые получила модель: возможно, модель их придумала.':
        'The references and figures in these findings were found neither in the document nor in the reference fragments the model received: the model may have made them up.',
    'разделы: {v}':
        'sections: {v}',
    'ответ модели не разобран':
        "the model's answer could not be parsed",
    'начало документа':
        'beginning of the document',
    'Не выполнено: {err}':
        'Not done: {err}',
    'Объединено групп повторов: {g}; замечаний было {a}, стало {b}.':
        'Groups of duplicates merged: {g}; findings before: {a}, after: {b}.',
    'Опечатки — без модели: было {a}, стало {b}.':
        'Typos — without the model: before {a}, after {b}.',
    'Убрано замечаний, где модель сама пишет, что проблемы нет: {n}.':
        'Findings removed where the model itself says there is no problem: {n}.',
    'Группы повторов:':
        'Groups of duplicates:',
    'Оставлено: «{t}»':
        'Kept: "{t}"',
    'влито: {v}':
        'merged in: {v}',
    'отдельно (тот же ответ модели): {v}':
        'kept apart (same model answer): {v}',
    'нашли проверок: {n}':
        'found by checks: {n}',
    '**Сверх лимита (в заключение не вошли):**':
        '**Over the limit (not in the report):**',
    'непонятный вердикт: {v}':
        'unclear verdict: {v}',
    'не сверены пункты {n} — {why}':
        'items {n} were not compared — {why}',
    'ответ модели не разобран: «{v}»':
        'the model\'s answer could not be parsed: "{v}"',
    'Часть {n}/{t}':
        'Part {n}/{t}',
    'Особое внимание {n}':
        'Special attention {n}',
    'Чек-лист {n}':
        'Checklist {n}',
    'Карточка системы {n}':
        'System card {n}',
    '[… документ целиком — {n} симв., как в загруженном файле …]':
        '[… the whole document — {n} chars, as in the uploaded file …]',
    '[… пропущено {n} симв. …]':
        '[… {n} chars skipped …]',
    '# Сырые ответы модели: {f}':
        '# Raw model answers: {f}',
    'Каждый запрос к модели во время аудита и сверки с эталоном: какая проверка спросила, что спросили (начало и конец запроса; документ целиком заменён пометкой) и что модель ответила — слово в слово, до того как MINT разобрал ответ на замечания.':
        'Every request to the model during the review and the comparison with the reference: which check asked, what was asked (the start and end of the request; the whole document is replaced by a note) and what the model answered — word for word, before MINT parsed the answer into findings.',
    '**Запросов:** {n}; **модель:** {m}.':
        '**Requests:** {n}; **model:** {m}.',
    'Без подписи':
        'Unlabelled',
    '**Системный промпт** ({n} симв.):':
        '**System prompt** ({n} chars):',
    '**Запрос** ({n} симв.):':
        '**Request** ({n} chars):',
    '**Ответ модели** ({n} симв., как есть):':
        '**Model answer** ({n} chars, as is):',
    '📥 Скачать сырые ответы модели (.md)':
        '📥 Download raw model answers (.md)',
    'Сырые_ответы_{v}.md':
        'Raw_answers_{v}.md',
    'Каждый запрос к модели во время аудита и сверки с эталоном и её ответ слово в слово — до разбора на замечания. Файл большой; нужен, чтобы разобрать спорный случай.':
        'Every request to the model during the review and the comparison with the reference, and its answer word for word — before parsing into findings. The file is large; it is for looking into a disputed case.',
    'Шлюз просил реже (HTTP 429)':
        'Gateway asked to slow down (HTTP 429)',
    '{n} раз, общие паузы {s} с — если повторяется, уменьшите «Аудит: запросов к модели одновременно»':
        '{n} times, shared pauses {s} s — if it repeats, lower "Review: requests to the model at the same time"',
    'Проверки без модели':
        'Checks without the model',
    'Сведение повторов':
        'Merging duplicates',
    'Документ в проверке раздела':
        'Document in the section review',
    '❌ Ответ не получен: {err}':
        '❌ No answer received: {err}',
    'Замечаний по пункту нет.':
        'No findings on this point.',
    '(не найдено: {v})':
        '(not found: {v})',
    '{tok} (×{n}, впервые — «{where}»)':
        '{tok} (×{n}, first in “{where}”)',
    ' и ещё {n}':
        ' and {n} more',
    'Не подтверждено источником':
        'Not confirmed by a source',
    'Сокращения используются без расшифровки — их нет в разделе «{h}»: {v}. Добавьте их в перечень.':
        'Abbreviations are used without being defined — they are not in the “{h}” section: {v}. Add them to the list.',
    'В разделе «{h}» расшифрованы сокращения, которых нет в тексте документа: {v}.':
        'The “{h}” section defines abbreviations that do not appear in the text of the document: {v}.',
    'В документе нет перечня сокращений; без расшифровки используются: {v}.':
        'The document has no list of abbreviations; used without a definition: {v}.',
    'есть в другом разделе документа: «{q}»':
        'present in another section of the document: “{q}”',
    'Ответ: {v}':
        'Answer: {v}',
    'Замечаний нет.':
        'No findings.',
    'не найдено: {v}':
        'not found: {v}',
    'Ответ на пункт «особого внимания»':
        'Answer to a “special attention” point',
    'Отдельный шаг на весь документ: ответ на каждый пункт поля «Особое внимание» и замечания по нему. Строка «Ответ:» и теги критичности обязательны.':
        'A separate step over the whole document: an answer to each point of the “Special attention” field and the findings on it. The “Answer:” line and the severity tags are required.',
    'Сверка «не описано» с документом':
        'Checking “not described” against the document',
    'Когда документ целиком не помещается в окно модели: есть ли в других разделах то, чего по замечанию нет. JSON-поля обязательны.':
        "When the whole document does not fit into the model's context window: whether other sections contain what a finding says is missing. The JSON fields are required.",
    'Последний шаг аудита: группы замечаний об одном и том же недостатке. Формат ответа — JSON-массив групп номеров.':
        'The last step of the review: groups of findings about the same shortcoming. The answer format is a JSON array of groups of numbers.',
    '(продолжение таблицы: строки с {n}-й, шапка повторена)':
        '(table continued: rows from {n}, header repeated)',
    '🎯 Особое внимание: «{item}»':
        '🎯 Special attention: “{item}”',
    'Весь документ в каждой проверке раздела':
        'Whole document in every section review',
    'Если документ помещается в окно модели, каждый раздел проверяется вместе с документом целиком: модель видит связи между разделами и не пишет «не описано» о том, что есть в другом разделе. Не помещается или выключено — модель получает оглавление, а замечания «не описано» сверяются с другими разделами.':
        "If the document fits into the model's context window, each section is reviewed together with the whole document: the model sees the links between sections and does not write “not described” about what is in another section. If it does not fit or this is off, the model gets the outline, and “not described” findings are checked against other sections.",
    'Сводить повторы замечаний моделью (+1 вызов LLM)':
        'Merge duplicate findings with the model (+1 LLM call)',
    'В конце аудита модель получает список всех замечаний и объединяет совпадающие по смыслу — из разных разделов и из ответов на «особое внимание». Выключено — повторы склеиваются только при совпадении слов.':
        'At the end of the review the model gets the list of all findings and merges those with the same meaning — from different sections and from the answers to “special attention”. When off, duplicates are merged only when their words match.',
    'Каждый раздел проверяется вместе с документом целиком.':
        'Each section is reviewed together with the whole document.',
    'Документ целиком не помещается в окно модели: к разделам прилагается оглавление.':
        "The whole document does not fit into the model's context window: the outline is attached to the sections.",
    'Документ проверяется одной частью.':
        'The document is reviewed as a single part.',
    '[Не подтверждено источником: {v}] {finding}':
        '[Not confirmed by a source: {v}] {finding}',
    '🔤 Проверка сокращений: ':
        '🔤 Abbreviation check: ',
    '🧩 Сведение повторов не выполнено: {err}':
        '🧩 Duplicates were not merged: {err}',
    '🧩 Повторы сведены: групп {g}, замечаний было {a}, стало {b}.':
        '🧩 Duplicates merged: {g} groups, findings before: {a}, after: {b}.',
    '## 📋 ЗАМЕЧАНИЯ ПО РАЗДЕЛАМ ДОКУМЕНТА\n{risks_block}\n{failed_block}':
        '## 📋 FINDINGS BY DOCUMENT SECTION\n{risks_block}\n{failed_block}',
    '✅ найдено':
        '✅ found',
    '⚠️ частично':
        '⚠️ partly',
    '❌ не найдено':
        '❌ not found',
    '❓ не сверено':
        '❓ not compared',
    'эталон пуст: впишите замечания, по одному на строку':
        'the reference is empty: enter the findings, one per line',
    '# Сверка с эталоном: {filename}':
        '# Comparison with the reference: {filename}',
    '**Модель:** {m}; **найдено:** {f} из {n}, **частично:** {p}, **не найдено:** {x}.':
        '**Model:** {m}; **found:** {f} of {n}, **partly:** {p}, **not found:** {x}.',
    '| № | Эталон | Вердикт | Что нашёл аудит | Комментарий |':
        '| No. | Reference | Verdict | What the review found | Comment |',
    'Глубокая проверка':
        'Deep review',
    '⚠️ Сверка не выполнена: {err}':
        '⚠️ The comparison was not done: {err}',
    'выключена':
        'off',
    '_Глубокая проверка: {v}._':
        '_Deep review: {v}._',
    '**Не выполнено:** {report}':
        '**Not done:** {report}',
    'Шаг {n}: {body}':
        'Step {n}: {body}',
    '(сведений и требований к процессу в документе не найдено)':
        '(no process information or requirements found in the document)',
    'Пункты оформлены обычным текстом, а не заголовком (стилем заголовка): {v}. Поэтому они не попадают в структуру документа и в содержание.':
        'Clauses formatted as plain text instead of a heading (heading style): {v}. So they are not in the document structure or the table of contents.',
    'Разделы без текста: {v}.':
        'Sections without text: {v}.',
    'список':
        'list',
    'разделы «Шаг N»':
        '“Step N” sections',
    '«{s}» — {k}, шагов: {n}':
        '“{s}” — {k}, steps: {n}',
    'Процесс в документе (глубокая проверка)':
        'Process in the document (deep review)',
    'не найден: шаги процесса ищутся в таблицах операций, списках шагов и подразделах «Шаг N»':
        'not found: process steps are looked for in tables of operations, lists of steps and “Step N” subsections',
    'Согласованность цифр':
        'Consistency of figures',
    'Утверждения части «{s}»':
        'Statements of the part “{s}”',
    'Опечатки: «{s}»':
        'Typos: “{s}”',
    'Противоречия: {t}':
        'Contradictions: {t}',
    'Утверждений нет.':
        'No statements.',
    'Проверьте согласованность показателей: {v}':
        'Check the consistency of the indicators: {v}',
    '«{a}» ({av}, раздел «{sa}») × {k} = {est}; «{b}» — {bv} (раздел «{sb}»): {how} в {r} раза':
        '“{a}” ({av}, section “{sa}”) × {k} = {est}; “{b}” — {bv} (section “{sb}”): {r} times {how}',
    'Среднее «{a}» ({av}) больше максимума «{b}» ({bv})':
        'The average “{a}” ({av}) is greater than the maximum “{b}” ({bv})',
    'В содержании есть разделы, которых нет среди заголовков документа: {v}.':
        'The contents list sections that are not among the headings of the document: {v}.',
    'Разделы документа, которых нет в содержании: {v}.':
        'Sections of the document missing from the contents: {v}.',
    'Таблица в разделе «{s}» не заполнена.':
        'The table in the section “{s}” is not filled in.',
    'Границы процесса «{s}»':
        'Process boundaries “{s}”',
    'Процесс «{s}»: шаг {a} → шаг {b}':
        'Process “{s}”: step {a} → step {b}',
    'Процесс «{s}»: требование «{r}»':
        'Process “{s}”: requirement “{r}”',
    'В таблице раздела «{s}» не заполнено: {v}.':
        'In the table of the section “{s}” these are not filled in: {v}.',
    'В таблице раздела «{s}» не заполнены колонки: {v}.':
        'In the table of the section “{s}” these columns are not filled in: {v}.',
    'расхождений больше чем вдвое не найдено':
        'no discrepancies of more than a factor of two found',
    'больше':
        'greater',
    'меньше':
        'smaller',
    'Процесс: переход между шагами':
        'Process: transition between steps',
    'Для каждой пары соседних шагов процесса (таблица операций, список шагов или разделы «Шаг N»): откуда вход, кто передаёт, может ли получатель обработать данные, совпадает ли с требованиями.':
        'For each pair of neighbouring process steps (a table of operations, a list of steps or “Step N” sections): where the input comes from, who passes it on, whether the recipient can process the data, whether it matches the requirements.',
    'Процесс: требование и шаги':
        'Process: requirement and steps',
    'Для каждого требования к процессу: есть ли шаг, который его выполняет, и нет ли шага, который ему противоречит.':
        'For each process requirement: whether there is a step that fulfils it and no step that contradicts it.',
    'Процесс: границы и результаты':
        'Process: boundaries and results',
    'Первый и последний шаг процесса — по границам процесса; шаг для каждого результата и потребителя; участники и системы.':
        'The first and last process step against the process boundaries; a step for each result and consumer; participants and systems.',
    'Утверждения раздела':
        'Statements of a section',
    'Из каждой части — утверждения для сверки с другими разделами, с темой из списка. JSON-поля обязательны.':
        'From each part — statements to check against other sections, with a topic from the list. The JSON fields are required.',
    'Противоречия между разделами':
        'Contradictions between sections',
    'Утверждения разных разделов на одну тему: есть ли противоречия.':
        'Statements of different sections on one topic: are there contradictions.',
    'Показатели документа и расчёты программы: сходятся ли объёмы, среднее и максимум, одинаковые показатели в разных разделах.':
        "The document's indicators and the program's calculations: whether volumes, averages and maximums, and the same indicators in different sections agree.",
    'Опечатки':
        'Typos',
    'Явные опечатки и грамматические ошибки в каждой части.':
        'Obvious typos and grammatical errors in each part.',
    'Сверка с эталоном':
        'Comparison with a reference',
    'Какие замечания эталона нашёл аудит. JSON-поля и коды вердиктов обязательны.':
        'Which reference findings the review found. The JSON fields and verdict codes are required.',
    '🔬 Глубокая проверка: вопросов — {n}, замечаний — {f}, не выполнено — {x}':
        '🔬 Deep review: questions — {n}, findings — {f}, not done — {x}',
    'Глубокая проверка: вопросов модели, не больше':
        'Deep review: questions to the model, at most',
    '🔬 Глубокая проверка (процесс по шагам, противоречия, цифры, опечатки)':
        '🔬 Deep review (process step by step, contradictions, figures, typos)',
    '📏 Сверка с эталоном — что нашла модель из ожидаемых замечаний':
        '📏 Comparison with a reference — which expected findings the model found',
    'Ожидаемые замечания (по одному на строку):':
        'Expected findings (one per line):',
    '📏 Сверить с эталоном':
        '📏 Compare with the reference',
    'Кроме проверки разделов модель отвечает на много узких вопросов: каждая пара соседних шагов процесса (таблица операций, список шагов или разделы «Шаг N»), каждое требование к процессу, границы процесса; утверждения разных разделов на одну тему; согласованность цифр (расчёт делает программа); опечатки. Узкий вопрос надёжно решает и модель среднего размера. Это десятки коротких вызовов LLM (не больше {n}, по {p} одновременно).':
        'Besides reviewing the sections, the model answers many narrow questions: each pair of neighbouring process steps (a table of operations, a list of steps or “Step N” sections), each process requirement, the process boundaries; statements of different sections on one topic; consistency of figures (the program does the arithmetic); typos. A medium-sized model handles a narrow question reliably. These are dozens of short LLM calls (at most {n}, {p} at a time).',
    'Замечания эксперта или прошлого согласования этого документа. Модель сверяет их с заключением: то же место и та же суть, формулировка может отличаться (+1 вызов LLM). Прогоните аудит с другой моделью или настройками и сверьте снова — так видно, какая модель что находит.':
        'Findings of an expert or of a previous approval of this document. The model compares them with the report: the same place and the same substance, the wording may differ (+1 LLM call). Run the review with another model or settings and compare again — this shows which model finds what.',
    '📥 Скачать сверку (.md)':
        '📥 Download the comparison (.md)',
    'Сверка с эталоном...':
        'Comparing with the reference...',
    'Сверка_с_эталоном_{v}.md':
        'Reference_comparison_{v}.md',
    '🔬 Глубокая проверка: вопросов модели — {n}, по {p} одновременно.':
        '🔬 Deep review: questions to the model — {n}, {p} at a time.',
    'Пропущено по лимиту: {s}.':
        'Skipped by the limit: {s}.',
    'шаг {n} — {v}':
        'step {n} — {v}',
    'В таблице операций раздела «{s}» не заполнено: {v}.':
        'In the table of operations of the section “{s}” these are not filled in: {v}.',
    'весь документ одним запросом ({n} симв.)':
        'the whole document in one request ({n} chars)',
    '📄 Весь документ одним запросом (для сравнения)':
        '📄 Whole document in one request (for comparison)',
    'Вместо проверки по разделам модель получает весь документ и пишет все замечания одним ответом (до {t} токенов, таймаут не меньше {s} с). Быстрее и без повторов, но модели среднего размера в таком режиме обычно находят меньше конкретных замечаний. Сравните оба режима «Сверкой с эталоном». Не помещается в окно модели — проверка по разделам.':
        "Instead of reviewing by section, the model gets the whole document and writes all findings in one answer (up to {t} tokens, a timeout of at least {s} s). Faster and without duplicates, but medium-sized models usually find fewer specific findings this way. Compare both modes with “Comparison with a reference”. If it does not fit into the model's window — review by section.",
    'Документ ({c} симв.) не помещается в окно модели одним запросом (места — {r} симв.): проверка по разделам. Задайте настоящее окно в «Модели и лимиты».':
        "The document ({c} chars) does not fit into the model's window in one request (room — {r} chars): review by section. Set the real window in “Models and limits”.",
    '📜 Весь документ ({chars} симв.) проверяется одним запросом.':
        '📜 The whole document ({chars} chars) is reviewed in one request.',
    '📜 Документ разбит на части по разделам: {n_sections} (до {audit_map_size} симв.).':
        '📜 The document is split into parts by section: {n_sections} (up to {audit_map_size} chars).',
    'вопросов модели: {n}; не выполнено: {f}; пропущено по лимиту: {s}; заняла {t} с (вопросы шли параллельно, в сумме — {sum} с)':
        'questions to the model: {n}; not done: {f}; skipped by the limit: {s}; took {t} s (the questions ran in parallel, {sum} s in total)',
    '**Замечаний в заключении:** {t}; из них к эталону относятся {m} — остальные стоит просмотреть: полезные или лишние.':
        '**Findings in the report:** {t}; {m} of them match the reference — look through the rest: useful or superfluous.',
    'Время аудита (по часам), с':
        'Review time (wall clock), s',
    'Время проверки разделов (сумма по разделам), с':
        'Section review time (sum over sections), s',
    'Запросов к модели одновременно':
        'Requests to the model at the same time',
    'Главных замечаний нет — только мелкие и опечатки (ниже).':
        'No main findings — only minor ones and typos (below).',
    '…и ещё {n} замечаний сверх потолка {cap} на один ответ (сначала оставлены критичные)':
        '…and {n} more findings above the limit of {cap} per answer (critical ones were kept first)',
    '## ✏️ ОПЕЧАТКИ И ГРАММАТИКА ({n})':
        '## ✏️ TYPOS AND GRAMMAR ({n})',
    '## 📝 МЕЛКИЕ И ОБЩИЕ ЗАМЕЧАНИЯ ({n}) — без цитаты и указания места':
        '## 📝 MINOR AND GENERAL FINDINGS ({n}) — without a quote or a place in the document',
    'Аудит: обрывать слишком длинный или зациклившийся ответ':
        'Review: cut off a too long or looping answer',
    'Ответы в аудите MINT получает потоком и обрывает сам, если ответ ушёл далеко за «Макс. длину ответа» (шлюз может её не соблюдать) или модель начала повторять одни и те же строки — иначе такой ответ занимает минуты. Шлюз, который не умеет отвечать потоком, получает обычный запрос.':
        'In the review MINT receives answers as a stream and cuts them off itself if an answer goes far beyond the “Max answer length” (the gateway may ignore it) or the model starts repeating the same lines — otherwise such an answer takes minutes. A gateway that cannot stream gets an ordinary request.',
    'Да — {y}, частично — {p}, нет — {n}, не относится — {na}':
        'Yes — {y}, partially — {p}, no — {n}, not applicable — {na}',
    '✅ есть':
        '✅ available',
    '🗓️ в планах':
        '🗓️ planned',
    '🛠️ нужна доработка':
        '🛠️ change needed',
    '⛔ противоречие':
        '⛔ conflict',
    '❓ неясно':
        '❓ unclear',
    '## ✅ ЧЕК-ЛИСТ «{t}»':
        '## ✅ CHECKLIST “{t}”',
    '## ✅ ЧЕК-ЛИСТ':
        '## ✅ CHECKLIST',
    ', без ясного ответа — {u}':
        ', no clear answer — {u}',
    ', ответ не получен — {f}':
        ', no answer received — {f}',
    '## 🧩 ЧТО ДОКУМЕНТ ТРЕБУЕТ ОТ СИСТЕМ':
        '## 🧩 WHAT THE DOCUMENT REQUIRES FROM SYSTEMS',
    'По карточкам систем из базы знаний: что система умеет сейчас, что в планах, где нужна доработка.':
        'From the system cards in the knowledge base: what the system can do now, what is planned, where a change is needed.',
    '_Карточка: {card}; упоминаний в документе: {n}._':
        '_Card: {card}; mentions in the document: {n}._',
    '✅ Чек-лист: «{item}»':
        '✅ Checklist: “{item}”',
    '🧩 Система «{item}» (карточка {card})':
        '🧩 System “{item}” (card {card})',
    'Чек-лист':
        'Checklist',
    'Правила экспертов (учитывать всегда)':
        'Expert rules (always use)',
    'Карточки систем':
        'System cards',
    'Системы, упомянутые в документе':
        'Systems mentioned in the document',
    'Правила и карточки на запрос (audit_pinned_max_chars)':
        'Rules and cards per request (audit_pinned_max_chars)',
    'Ответ без пояснения.':
        'Answer without an explanation.',
    'Замечания — в ответах на пункты выше.':
        'The findings are in the answers to the items above.',
    'Требований к системе нет.':
        'No requirements for the system.',
    '{t}: пунктов {n}':
        '{t}: {n} items',
    '**Замечания:**':
        '**Findings:**',
    '{name} — {n} упом.':
        '{name} — {n} mentions',
    'общие пункты':
        'common items',
    '**Тип документа**: {v}\n':
        '**Document type**: {v}\n',
    'Пункт чек-листа':
        'Checklist item',
    'Ответ на каждый пункт чек-листа по типу документа — по всему документу. Строка «Ответ:» со словом «да / частично / нет / не относится» и теги критичности обязательны.':
        'An answer to each item of the checklist for the document type — over the whole document. The “Answer:” line with the word “yes / partially / no / not applicable” and the severity tags are required.',
    'Правила экспертов и карточки систем':
        'Expert rules and system cards',
    'Заголовок блока с документами базы «учитывать в аудите всегда» и карточками упомянутых систем: они передаются модели в каждой проверке, отдельно от найденных норм.':
        'Header of the block with knowledge base documents marked “always use in the review” and the cards of mentioned systems: the model gets them in every check, separately from the norms found.',
    'Что документ требует от системы':
        'What the document requires from the system',
    'По карточке каждой системы, упомянутой в документе: требования документа к системе со статусами «есть / в планах / доработка / противоречие / неясно» и замечания. Статусы и теги критичности обязательны.':
        'From the card of each system mentioned in the document: the requirements of the document to the system with the statuses “available / planned / change / conflict / unclear” and findings. The statuses and severity tags are required.',
    'Аудит: запросов к модели одновременно':
        'Review: requests to the model at the same time',
    'Сколько запросов аудита отправлять шлюзу одновременно: проверки разделов, вопросы глубокой проверки, пункты особого внимания и чек-листа. Больше — быстрее; если шлюз отвечает 429 или таймаутами — уменьшите.':
        'How many review requests to send to the gateway at the same time: section checks, deep review questions, special attention and checklist items. More is faster; if the gateway answers 429 or times out, reduce it.',
    'Правила экспертов и карточки систем на запрос (симв.)':
        'Expert rules and system cards per request (chars)',
    'Документы базы «учитывать в аудите всегда» и карточки систем, упомянутых в проверяемом тексте, идут модели в каждой проверке — сверх нормативного контекста. Помещаются — целиком, иначе — самые близкие к тексту фрагменты. 0 — не передавать.':
        'Knowledge base documents marked “always use in the review” and the cards of systems mentioned in the text under review go to the model in every check — on top of the normative context. If they fit, in full, otherwise the fragments closest to the text. 0 — do not pass them.',
    'Что документ требует от систем (по карточкам)':
        'What the document requires from systems (by cards)',
    'По каждой системе с карточкой в базе, упомянутой в документе не меньше двух раз, модель выписывает требования документа к системе: есть, в планах, нужна доработка, противоречие, неясно (+1 вызов LLM на систему).':
        'For each system with a card in the knowledge base that is mentioned in the document at least twice, the model lists the requirements of the document to the system: available, planned, change needed, conflict, unclear (+1 LLM call per system).',
    '📌 Для аудита: правила экспертов и карточки систем ({n})':
        '📌 For the review: expert rules and system cards ({n})',
    'Обычные документы аудит находит поиском по каждому разделу. Отмеченные здесь модель получает в каждой проверке, сверх нормативного контекста (лимит — «Экспертные настройки» → «Правила экспертов и карточки систем на запрос»).':
        'Ordinary documents are found by the review by searching for each section. The model gets the ones marked here in every check, on top of the normative context (limit — “Expert settings” → “Expert rules and system cards per request”).',
    '📌 Учитывать в аудите всегда (правила экспертов)':
        '📌 Always use in the review (expert rules)',
    '🗂️ Карточки систем':
        '🗂️ System cards',
    'Документ с правилами, которые проверяются в каждом документе: модель получает его целиком, а если не помещается — самые близкие к проверяемому разделу фрагменты. Пишите правила так, чтобы каждое было понятно само по себе: когда применяется, правило, типичная ошибка, основание.':
        'A document with rules that are checked in every document: the model gets it in full, and if it does not fit, the fragments closest to the section under review. Write the rules so that each one is clear on its own: when it applies, the rule, a typical mistake, the grounds.',
    'Карточка — что система умеет сейчас, что в планах и к какому сроку, ограничения, как к ней подключаются. Подключается к проверке, когда система упоминается в разделе; по каждой системе, упомянутой в документе не меньше двух раз, модель выписывает, что документ от неё требует. Названия системы MINT берёт из строки «Названия: …» в начале карточки и из её заголовка.':
        'A card is what the system can do now, what is planned and by when, its limitations, how to connect to it. It is added to a check when the system is mentioned in the section; for each system mentioned in the document at least twice, the model lists what the document requires from it. MINT takes the names of the system from the “Names: …” line at the start of the card and from its heading.',
    '🗂️ {file}: MINT узнаёт систему по названиям — {names}':
        '🗂️ {file}: MINT recognises the system by the names {names}',
    '📋 Чек-лист: {t} — пунктов {n}':
        '📋 Checklist: {t} — {n} items',
    '📋 Чек-лист: выключен':
        '📋 Checklist: off',
    'Новый тип документа:':
        'New document type:',
    'Слова для распознавания (через «;»):':
        'Words to recognise it (separated by “;”):',
    '➕ Добавить тип':
        '➕ Add type',
    'Проверить документ по чек-листу (+1 вызов LLM на пункт)':
        'Check the document against the checklist (+1 LLM call per item)',
    'Тип документа':
        'Document type',
    'Общие пункты (для любого документа), по одному на строку:':
        'Common items (for any document), one per line:',
    'Чек-листы: {v}. Правки выше действуют на этот прогон; «Сохранить» записывает их в {own} — этот файл не попадает в репозиторий и не затирается при обновлении.':
        'Checklists: {v}. The edits above apply to this run; “Save” writes them to {own} — this file does not go into the repository and is not overwritten by updates.',
    '💾 Сохранить пункты в чек-листы':
        '💾 Save the items to the checklists',
    '⚙️ Типы документов: добавить, изменить слова, удалить':
        '⚙️ Document types: add, change words, delete',
    'Слова, по которым узнаётся «{t}» (через «;»):':
        'Words by which “{t}” is recognised (separated by “;”):',
    'Например: Задание на доработку':
        'For example: Change request',
    'например: задание на доработку; заданию на доработку':
        'for example: change request; request for change',
    'Авто — по словам из названия документа (имя файла и начало документа), их список — у каждого типа в чек-листах. Каждый пункт — отдельный вопрос модели по всему документу; ответ «да / частично / нет / не относится» и замечания — в блоке «Чек-лист» заключения.':
        'Auto — by words from the title of the document (the file name and the start of the document); each type in the checklists has its list of words. Each item is a separate question to the model over the whole document; the answer “yes / partially / no / not applicable” and the findings are in the “Checklist” block of the conclusion.',
    'Пункты для типа «{t}», по одному на строку:':
        'Items for the type “{t}”, one per line:',
    'Пунктов {n} — проверяются первые {m}.':
        '{n} items — the first {m} are checked.',
    'свой файл {p}':
        'your own file {p}',
    'образец {p} (свой файл ещё не создан)':
        'the example {p} (your own file is not created yet)',
    'чек-листов нет':
        'no checklists',
    'Сохранено: {p}':
        'Saved: {p}',
    '💾 Сохранить слова':
        '💾 Save the words',
    '🗑️ Удалить тип «{t}»':
        '🗑️ Delete the type “{t}”',
    'Тип «{t}» уже есть.':
        'The type “{t}” already exists.',
    'Тип определён по словам «{w}».':
        'The type is recognised by the words “{w}”.',
    'Тип не определён: в начале документа нет слов ни одного типа — будут только общие пункты.':
        'The type is not recognised: the start of the document has no words of any type — only the common items will be checked.',
    'Авто: {t}':
        'Auto: {t}',
    'Авто: тип не определён':
        'Auto: type not recognised',
    'Без типа — только общие пункты':
        'No type — common items only',
    '📋 Вопросы по всему документу: {v} (по {p} одновременно).':
        '📋 Questions over the whole document: {v} ({p} at a time).',
    'особое внимание — {n}':
        'special attention — {n}',
    'чек-лист — {n}':
        'checklist — {n}',
    'требования к системам — {v}':
        'requirements to systems — {v}',
    'Документ в целом':
        'The document as a whole',
    'также: {v}':
        'also: {v}',
    'о пункте {c}: его проверяет своя часть документа':
        'about clause {c}: its own part of the document checks it',
    'включены для аудита (audit_reasoning): ответ до {n} токенов вместе с рассуждениями, таймаут {t} с':
        'enabled for the review (audit_reasoning): answer up to {n} tokens including reasoning, timeout {t} s',
    '## ⭐ ГЛАВНОЕ':
        '## ⭐ KEY POINTS',
    'Температура проходов 2–3: {t}. Их замечания сведены вместе с первым проходом; «найдено: …» у замечания в заключении считает и проходы.':
        'Temperature of passes 2–3: {t}. Their findings are merged with the first pass; “found: …” next to a finding in the report counts the passes too.',
    'Выключено в настройках (audit_summary_max = 0).':
        'Turned off in the settings (audit_summary_max = 0).',
    'найдено: {n} (проверок — {c}, проходов — {p})':
        'found: {n} (checks — {c}, passes — {p})',
    'особое внимание {i}, №{n}':
        'special attention {i}, no. {n}',
    'чек-лист {i}, №{n}':
        'checklist {i}, no. {n}',
    'в ответе модели нет номеров из списка':
        'the model answer has no numbers from the list',
    '_Самые важные замечания, по мнению модели-редактора; подробности и цитаты — в замечаниях по номерам ниже._':
        '_The most important findings, as chosen by the editor model; details and quotes are in the findings with these numbers below._',
    '_Самые важные замечания — найденные несколькими проверками и критичные; подробности — в замечаниях по номерам ниже._':
        '_The most important findings — those found by several checks and critical ones; details are in the findings with these numbers below._',
    '### Проход {n}: разделов — {s}, вопросов глубокой проверки — {d}, замечаний — {f}, не выполнено — {x}; {t} с':
        '### Pass {n}: sections — {s}, deep review questions — {d}, findings — {f}, failed — {x}; {t} s',
    'но llm_extra_body их выключает — свои параметры запроса важнее':
        'but llm_extra_body turns it off — custom request parameters take precedence',
    'модель рассуждала':
        'the model did reason',
    'рассуждений в ответах не было: шлюз мог их не включить — включатель задаётся в llm_extra_body':
        'the answers had no reasoning: the gateway may not have turned it on — set the switch in llm_extra_body',
    'Не выбрано моделью: {err} — взяты найденные несколькими проверками и критичные: {n}.':
        'Not chosen by the model: {err} — taken those found by several checks and critical ones: {n}.',
    'Выбрано моделью: {n} из {m} замечаний.':
        'Chosen by the model: {n} of {m} findings.',
    'Главное':
        'Key points',
    'Проходов проверки (audit_passes)':
        'Review passes (audit_passes)',
    'система «{s}», №{n}':
        'system “{s}”, no. {n}',
    'Проход {n}':
        'Pass {n}',
    'Проходы 2–{n}':
        'Passes 2–{n}',
    '№{n}':
        'no. {n}',
    '**Часть {part}/{total} — «{preview}»**':
        '**Part {part}/{total} — “{preview}”**',
    '«Главное» в начале заключения':
        '“Key points” at the top of the report',
    'Из всех замечаний — самые важные (не больше audit_summary_max), каждое одной строкой: в начале заключения они идут указателями на замечания по номерам. Формат ответа — JSON-массив с полями n и gist.':
        'Of all findings, the most important ones (at most audit_summary_max), one line each: at the top of the report they point to the findings by number. The answer format is a JSON array with the fields n and gist.',
    'Что делает аудит':
        'What the review does',
    'Качество и время':
        'Quality and time',
    'Объём контекста':
        'Context size',
    '🛡️ Самокритика':
        '🛡️ Self-critique',
    'После черновика замечаний второй проход «Старший контролёр» убирает надуманные замечания. +1 вызов LLM на раздел документа.':
        'After the draft of findings, a second pass, the “Senior controller”, removes far-fetched findings. +1 LLM call per document section.',
    '«Главное» в начале заключения: замечаний, не больше':
        '“Key points” at the top of the report: findings, at most',
    'Модель-редактор выбирает из всех замечаний самые важные и пишет суть каждого одной строкой — со ссылкой на номер замечания ниже (это указатель, а не копия: число замечаний не меняется). +1 вызов LLM. Модель не ответила — берутся найденные несколькими проверками и критичные. 0 — без блока.':
        'An editor model picks the most important of all findings and writes the gist of each in one line, with the number of the finding below (a pointer, not a copy: the number of findings does not change). +1 LLM call. If the model does not answer, the findings found by several checks and critical ones are taken. 0 — no block.',
    'Проходов проверки разделов и глубокой проверки':
        'Passes of the section check and the deep review',
    '2–3 — разделы и вопросы глубокой проверки о процессе, требованиях, цифрах и противоречиях проверяются ещё раз (температура не ниже 0,4), и замечания проходов сводятся вместе: то, что модель случайно пропустила в одном проходе, находит другой, а найденное несколько раз выше в заключении. Время и вызовы LLM — почти вдвое-втрое больше.':
        '2–3 — the sections and the deep review questions about the process, requirements, numbers and contradictions are checked again (temperature at least 0.4), and the findings of the passes are merged: what the model missed by chance in one pass, another finds, and what is found several times ranks higher in the report. Time and LLM calls — almost two to three times more.',
    'Аудит с рассуждениями модели':
        'Review with model reasoning',
    'Модель рассуждает перед каждым ответом аудита — даже если рассуждения выключены в «Языковой модели» (в чате остаются выключенными). Медленнее в разы: к длине ответа добавляется 6000 токенов на рассуждения, таймаут — не меньше 300 с. Включатель — стандартный параметр vLLM и SGLang; в логе видно, рассуждала ли модель на самом деле.':
        'The model reasons before every review answer — even if reasoning is turned off under “Language model” (it stays off in the chat). Several times slower: 6000 tokens for reasoning are added to the answer length, the timeout is at least 300 s. The switch is the standard vLLM and SGLang parameter; the log shows whether the model actually reasoned.',
    'Лимит коротких вызовов LLM в глубокой проверке (0 — без лимита) на один проход. Если вопросов больше, первыми идут процесс (шаги, требования, границы) и цифры, затем утверждения разделов и опечатки.':
        'Limit of short LLM calls in the deep review (0 — no limit) per pass. If there are more questions, the process (steps, requirements, boundaries) and numbers go first, then section statements and typos.',
    '📜 Настройки аудита — во вкладке «Аудит документа», блок «⚙️ Настройки аудита»: все в одном месте.':
        '📜 Review settings are on the “Document review” tab, block “⚙️ Review settings”: all in one place.',
    'Сейчас: база — {kb} · глубокая проверка — {deep} · проходов — {p} · рассуждения — {r} · самокритика — {c} · сведение повторов — {m} · «Главное» — {s}':
        'Now: knowledge base — {kb} · deep review — {deep} · passes — {p} · reasoning — {r} · self-critique — {c} · merging duplicates — {m} · “Key points” — {s}',
    'включены для аудита':
        'on for the review',
    '⚙️ Настройки аудита':
        '⚙️ Review settings',
    'Запрос аудита к модели: таймаут {t} с, ответ до {n} токенов, рассуждения — {r}. Модель, таймаут и длина ответа — в боковой панели («Модели и лимиты», «Экспертные настройки» → «Языковая модель»).':
        'A review request to the model: timeout {t} s, answer up to {n} tokens, reasoning — {r}. The model, timeout and answer length are in the sidebar (“Models and limits”, “Expert settings” → “Language model”).',
    'Значения действуют на время сеанса (✋ вручную); постоянные — в config.yaml, раздел audit. «↩️ Сбросить изменения сеанса» в «Экспертных настройках» возвращает и их.':
        'Values apply for the session (✋ manual); permanent ones are in config.yaml, section audit. “↩️ Reset session changes” in “Expert settings” resets them too.',
    'включены для аудита (таймаут не меньше {s} с)':
        'on for the review (timeout at least {s} s)',
    '🔂 Проход {n} из {t}: разделов — {s}, вопросов глубокой проверки — {d} (температура {temp}).':
        '🔂 Pass {n} of {t}: sections — {s}, deep review questions — {d} (temperature {temp}).',
    '⭐ «Главное» выбрано без модели ({err}): {n}.':
        '⭐ “Key points” chosen without the model ({err}): {n}.',
    '⭐ «Главное» — в начале заключения (замечаний: {n}).':
        '⭐ “Key points” — at the top of the report (findings: {n}).',
    'отдельно (другой шаг процесса): {v}':
        'kept apart (another process step): {v}',
    'Названия':
        'Names',
    '{system} полное название сокращение':
        '{system} full name abbreviation',
    'Как ещё называется {system} в документах: полное название, сокращения, названия частей? Каждый вариант написания — отдельной строкой.':
        'What other names does {system} have in the documents: full name, abbreviations, names of its parts? Each spelling on a separate line.',
    'Назначение':
        'Purpose',
    '{system} назначение пользователи смежные системы':
        '{system} purpose users neighbouring systems',
    'Для чего предназначена {system}, кто её пользователи и с какими системами она взаимодействует?':
        'What is {system} for, who are its users and which systems does it interact with?',
    'Сервисы и функции':
        'Services and functions',
    '{system} сервисы функции возможности':
        '{system} services functions capabilities',
    'Какие сервисы и функции {system} предоставляет смежным системам?':
        'Which services and functions does {system} provide to neighbouring systems?',
    'Лимиты и объёмы':
        'Limits and volumes',
    '{system} ограничения объём размер производительность время ответа режим работы':
        '{system} limits volume size performance response time operating hours',
    'Какие ограничения по объёму и производительности есть у {system}: размер сообщения или файла, количество в сутки, время ответа, режим работы? Цифры — с единицами измерения.':
        'What volume and performance limits does {system} have: message or file size, number per day, response time, operating hours? Numbers with units.',
    'Защита данных':
        'Data protection',
    '{system} шифрование электронная подпись сертификат ключи':
        '{system} encryption electronic signature certificate keys',
    'Как {system} защищает данные: подпись и шифрование, на чьих сертификатах, кто расшифровывает, где хранятся ключи?':
        'How does {system} protect data: signature and encryption, for whose certificates, who decrypts, where the keys are kept?',
    'Хранение данных':
        'Data storage',
    '{system} хранение данных срок хранения файлов':
        '{system} data storage file retention period',
    'Сколько и где {system} хранит данные и файлы и что с ними происходит по окончании срока хранения?':
        'How long and where does {system} keep data and files, and what happens to them when the retention period ends?',
    'Что в планах и к какому сроку':
        'What is planned and by when',
    '{system} планы развития доработки сроки релиз':
        '{system} roadmap planned changes dates release',
    'Какие доработки {system} запланированы и к каким срокам? Каждая — отдельной строкой: доработка — срок или релиз — статус.':
        'Which changes to {system} are planned and by when? Each on a separate line: change — date or release — status.',
    'Ограничения — чего система не умеет':
        'Limitations — what the system cannot do',
    '{system} не поддерживает ограничения запреты':
        '{system} not supported limitations restrictions',
    'Чего {system} не умеет или не поддерживает? Какие ограничения и запреты установлены для смежных систем?':
        'What can {system} not do or not support? Which limitations and restrictions apply to neighbouring systems?',
    'Как подключаются смежные системы':
        'How neighbouring systems connect',
    '{system} подключение смежной системы интеграция протокол формат заявка':
        '{system} connecting a neighbouring system integration protocol format request',
    'Как смежная система подключается к {system}: через какие платформы, по каким протоколам и в каких форматах; какие заявки, согласования и испытания нужны?':
        'How does a neighbouring system connect to {system}: through which platforms, over which protocols and in which formats; which requests, approvals and tests are needed?',
    'Требования к смежным системам':
        'Requirements for neighbouring systems',
    '{system} требования к смежным системам документации':
        '{system} requirements for neighbouring systems documentation',
    'Какие требования {system} предъявляет к смежным системам и к их документации?':
        'Which requirements does {system} set for neighbouring systems and their documentation?',
    'Что умеет сейчас':
        'What it can do now',
    '# Карточка системы «{system}»':
        '# System card "{system}"',
    'Названия: {names}':
        'Names: {names}',
    'Актуально на: {d} (черновик)':
        'As of: {d} (draft)',
    '⚠️ ЧЕРНОВИК: собран MINT по базе знаний {d}{model}. Проверьте каждый факт по источнику, допишите пробелы («нет в базе»), особенно ограничения и планы со сроками, и удалите эту пометку, прежде чем загружать карточку в базу.':
        '⚠️ DRAFT: put together by MINT from the knowledge base on {d}{model}. Check every fact against its source, fill in the gaps ("not in the base"), especially limitations and plans with dates, and remove this note before loading the card into the base.',
    '## Источники, по которым собран черновик':
        '## Sources the draft was put together from',
    'не указано название системы':
        'the system name is empty',
    '_Не получено: {err} — повторите сборку или допишите раздел._':
        '_Not received: {err} — put the draft together again or write the section._',
    '_Нет в базе — заполнит эксперт._':
        '_Not in the base — the expert fills it in._',
    '⚠️ проверьте: источник не найден среди фрагментов':
        '⚠️ check: the source is not among the fragments',
    ', модель {m}':
        ', model {m}',
    'Карточки систем':
        'System cards',
    'Черновик карточки: раздел':
        'Card draft: a section',
    'Черновик карточки системы по базе: на каждый раздел карточки — ответ только по найденным фрагментам, у каждого факта ссылка [Источник: …]. Фраза «НЕТ В БАЗЕ» обязательна: по ней MINT отмечает пробел для эксперта.':
        'A system card draft from the base: for each section of the card, an answer only from the fragments found, each fact with a [Source: …] reference. The phrase "NOT IN THE BASE" is required: by it MINT marks a gap for the expert.',
    'Карточка_{name}.md':
        'Card_{name}.md',
    '🗂️ Собрать черновик карточки системы по базе':
        '🗂️ Draft a system card from the base',
    '🗂️ Черновик карточки системы':
        '🗂️ System card draft',
    'Карточка — справка о системе для аудита: что умеет сейчас, что в планах и к какому сроку, ограничения, как подключаются смежные системы. MINT задаёт базе знаний по вопросу на каждый раздел ({n} вопросов) и пишет в черновик только найденное — у каждого факта ссылка на источник. Чего в базе нет, помечено «нет в базе»: это дописывает эксперт. Сначала загрузите в базу документацию системы и страницы вики о ней.':
        'A card is a reference on a system for the review: what it can do now, what is planned and by when, limitations, how neighbouring systems connect. MINT asks the knowledge base one question per section ({n} questions) and writes only what it finds into the draft — each fact with a reference to its source. What is not in the base is marked "not in the base": the expert fills it in. Load the system documentation and its wiki pages into the base first.',
    'Другие названия (через запятую, необязательно)':
        'Other names (comma-separated, optional)',
    '🗂️ Собрать черновик':
        '🗂️ Put the draft together',
    '**Черновик карточки «{s}»:** разделов со сведениями — {f} из {n}; фактов без подтверждённого источника — {u}; {t} с.':
        '**Card draft “{s}”:** sections with facts — {f} of {n}; facts without a confirmed source — {u}; {t} s.',
    '📥 Скачать черновик карточки (.md)':
        '📥 Download the card draft (.md)',
    'Дальше: проверьте каждый факт по источнику, допишите пробелы (особенно ограничения и планы со сроками) и удалите пометку «черновик» → загрузите карточку в базу (или положите в вики и загрузите оттуда) → отметьте её в «📌 Для аудита» → «🗂️ Карточки систем».':
        'Next: check every fact against its source, fill in the gaps (especially limitations and plans with dates) and remove the "draft" note → load the card into the base (or put it in the wiki and load it from there) → mark it in "📌 For the review" → "🗂️ System cards".',
    'MINT задаёт базе знаний узкие вопросы по разделам карточки и собирает черновик: у каждого факта — источник, пробелы помечены. Черновик проверяет и дописывает эксперт.':
        'MINT asks the knowledge base narrow questions by card section and puts a draft together: each fact with its source, gaps marked. The expert checks and completes the draft.',
    'Например: Система А':
        'For example: System A',
    'Сокращения и другие написания — попадут в строку «Названия:», по которой аудит узнаёт систему в документах. Найденные в базе варианты MINT добавит сам.':
        'Abbreviations and other spellings go into the "Names:" line by which the review recognises the system in documents. MINT adds the variants it finds in the base.',
    'Нет в базе — допишет эксперт: {v}.':
        'Not in the base — the expert fills in: {v}.',
    'Модель не ответила по разделам: {v} — соберите черновик ещё раз или допишите их.':
        'The model did not answer for the sections: {v} — put the draft together again or write them.',
    'Черновик карточки':
        'Card draft',
    'Вопросы к базе по разделам карточки...':
        'Asking the base by card section...',
    'не получено':
        'not received',
    'фактов: {n}':
        'facts: {n}',
    'нет в базе':
        'not in the base',
    '«{t}» — {s}':
        '“{t}” — {s}',
    'Черновик не собран: {e}':
        'The draft was not put together: {e}',
    # ---------------- документы-основания, повторы в кусках раздела
    "выключено":
        "off",
    "по шифру":
        "by code",
    "по названию":
        "by title",
    "выбран вручную":
        "chosen manually",
    "в базе нет: {v}":
        "not in the base: {v}",
    "не выбраны":
        "none chosen",
    "Повторы в кусках одного длинного раздела склеены без модели: {n}.":
        "Duplicates in the pieces of one long section merged without the model: {n}.",
    "Документы-основания (audit_basis_docs)":
        "Basis documents (audit_basis_docs)",
    "ссылок на документы-основания в документе нет":
        "the document does not refer to basis documents",
    "Документы-основания":
        "Basis documents",
    "Заголовок блока с фрагментами документов-оснований из базы — документов, по которым разработан проверяемый документ (ссылки на титуле и в «Ссылочных документах»): они передаются модели в каждой проверке, отдельно от найденных норм.":
        "Heading of the block with fragments of basis documents from the base — the documents the document under review was developed under (references on the title page and in \"Referenced documents\"): they go to the model in every check, separately from the norms found.",
    "📎 Документы-основания из базы":
        "📎 Basis documents from the base",
    "Документ называет своё основание — на титуле («разработан в соответствии с …») и в разделе «Ссылочные документы». Те из них, что есть в базе знаний (по шифру или названию), MINT подключает к каждой проверке раздела: фрагменты, ближайшие к разделу, — «документ должен им соответствовать». Какие найдены — в блоке «📎 Документы-основания» после загрузки документа; там же их можно снять или добавить.":
        "A document names its basis — on the title page (\"developed in accordance with …\") and in the \"Referenced documents\" section. Those of them that are in the knowledge base (by code or title) MINT adds to every section check: the fragments closest to the section — \"the document must comply with them\". Which ones were found is shown in the \"📎 Basis documents\" block after the document is uploaded; there you can remove or add them.",
    "Документы-основания на запрос (симв.)":
        "Basis documents per request (chars)",
    "Сколько текста документов-оснований (ближайшие к разделу фрагменты) идёт модели в каждой проверке — сверх нормативного контекста. 0 — не передавать.":
        "How much text of basis documents (the fragments closest to the section) goes to the model in every check — on top of the normative context. 0 — do not pass.",
    "📎 Документы-основания из базы: {n}":
        "📎 Basis documents from the base: {n}",
    "📎 Документы-основания: в базе не найдены":
        "📎 Basis documents: not found in the base",
    "📎 Документы-основания: документ на них не ссылается":
        "📎 Basis documents: the document does not refer to any",
    "Документы, по которым разработан проверяемый документ: MINT берёт ссылки с титула («в соответствии с …», «на основании …») и из раздела «Ссылочные документы» и ищет их в базе по шифру и названию. Их фрагменты, ближайшие к разделу, модель получает в каждой проверке — «документ должен им соответствовать».":
        "Documents the document under review was developed under: MINT takes the references from the title page (\"in accordance with …\", \"based on …\") and from the \"Referenced documents\" section and looks them up in the base by code and title. The model gets their fragments closest to the section in every check — \"the document must comply with them\".",
    "Документы базы — основания этого документа":
        "Base documents that are the basis of this document",
    "Снимите лишний или добавьте документ, которого MINT не узнал (например, техническое задание, по которому разработан документ). Лимит текста на один запрос — «⚙️ Настройки аудита» → «Документы-основания на запрос».":
        "Remove an extra one or add a document MINT did not recognise (for example, the specification the document was developed under). The text limit per request is in \"⚙️ Review settings\" → \"Basis documents per request\".",
    "📎 {src} — найден {by}: {ref}":
        "📎 {src} — found {by}: {ref}",
    "Нет в базе: {v}. Загрузите их в базу, если они нужны для проверки.":
        "Not in the base: {v}. Upload them to the base if the review needs them.",
    "📎 Документы-основания: {v}":
        "📎 Basis documents: {v}",

    # ---- разбор замечаний экспертом, сохранённые аудиты (mint/expert_review.py, mint/ui/audit_review.py, tab_audit.py)
    '# Замечания к документу «{f}»':
        '# Findings on the document “{f}”',
    'Дата: {d}':
        'Date: {d}',
    'Замечания к документу «{f}»':
        'Findings on the document “{f}”',
    '№':
        'No.',
    'Замечание':
        'Finding',
    'Критичность':
        'Severity',
    '—':
        '—',
    '✅ беру':
        '✅ keep',
    '➖ мелочь':
        '➖ minor',
    '❌ неверно':
        '❌ wrong',
    'в документе это есть':
        'the document has it',
    'модель не так поняла текст':
        'the model misread the text',
    'не относится к документу':
        'not relevant to the document',
    'так принято, это не ошибка':
        'common practice, not an error',
    'повтор другого замечания':
        'duplicates another finding',
    'другое':
        'other',
    'Глубокая: шаги процесса':
        'Deep: process steps',
    'Глубокая: требования к процессу':
        'Deep: process requirements',
    'Глубокая: границы процесса':
        'Deep: process boundaries',
    'Глубокая: цифры':
        'Deep: numbers',
    'Глубокая: противоречия':
        'Deep: contradictions',
    'Глубокая: утверждения':
        'Deep: statements',
    'Требования к системе':
        'System requirements',
    'Без модели':
        'Without the model',
    'основные':
        'main',
    'ответы на пункты':
        'answers to items',
    'не подтверждено':
        'not confirmed',
    'мелкие':
        'minor',
    'опечатки':
        'typos',
    'Версия MINT: {v}':
        'MINT version: {v}',
    'основные и ответы на пункты':
        'main and answers to items',
    '**📄 Мои замечания** — отмеченные ✅ и свои:':
        '**📄 My findings** — marked ✅ and your own:',
    'Включить и отмеченные ➖ мелочь':
        'Also include those marked ➖ minor',
    'Замечаний в списке: {n}.':
        'Findings in the list: {n}.',
    '**📤 Разбор для улучшения MINT** — какие проверки MINT ошибаются и что он пропускает:':
        '**📤 Assessment for improving MINT** — which MINT checks are wrong and what it misses:',
    'Без текстов замечаний':
        'Without finding texts',
    '📤 Скачать разбор (.json)':
        '📤 Download the assessment (.json)',
    'С текстами в файле есть цитаты документа — передавайте его только туда, куда можно передавать сам документ. Все разборы сразу — в «📂 Мои аудиты».':
        'With texts, the file contains quotes from the document — send it only where the document itself may be sent. All assessments at once — in "📂 Saved reviews".',
    '⭐ в «Главном»':
        '⭐ in "Key points"',
    '📎 по документу-основанию':
        '📎 per a basis document',
    '✍️ Разбор замечаний экспертом и «Мои замечания»':
        '✍️ Expert assessment of findings and "My findings"',
    '**➕ Свои замечания** — то, что MINT пропустил (строки добавляются внизу таблицы):':
        '**➕ Your own findings** — what MINT missed (add rows at the bottom of the table):',
    '📥 Мои замечания (.md)':
        '📥 My findings (.md)',
    'Только виды проверок, критичность, отметки и причины — без текстов замечаний, цитат, разделов, комментариев и имени файла. С текстами разбор полезнее: видно, в чём именно ошибка.':
        'Only check kinds, severity, marks and reasons — no finding texts, quotes, sections, comments or file name. With texts the assessment is more useful: it shows what exactly is wrong.',
    'Цитата: «{q}»':
        'Quote: “{q}”',
    'Не найдено ни в документе, ни в нормах: {v}':
        'Found neither in the document nor in the norms: {v}',
    'Отметка':
        'Mark',
    'Комментарий':
        'Comment',
    'По каждому замечанию: ✅ беру — замечание верное и войдёт в «Мои замечания»; ➖ мелочь — верное, но несущественное; ❌ неверно — выберите причину. Внизу — свои замечания, которых MINT не нашёл. Отметки сохраняются сразу: разбор можно продолжить позже в «📂 Мои аудиты».':
        'For each finding: ✅ keep — the finding is correct and goes into "My findings"; ➖ minor — correct but not significant; ❌ wrong — choose a reason. Below — your own findings that MINT did not find. Marks are saved at once: you can continue the assessment later in "📂 Saved reviews".',
    'Аудит не сохранён на диск — отметки действуют до конца сеанса.':
        'The review is not saved to disk — the marks last until the end of the session.',
    'Замечаний нет — можно добавить свои ниже.':
        'No findings — you can add your own below.',
    '📥 Мои замечания (.docx)':
        '📥 My findings (.docx)',
    'Замечания_{v}.md':
        'Findings_{v}.md',
    '📝 Документ с моими замечаниями':
        '📝 Document with my findings',
    'комментарий (необязательно)':
        'comment (optional)',
    'Размечено {m} из {n}: ✅ {ok} · ➖ {mi} · ❌ {w} · своих замечаний — {a}':
        'Marked {m} of {n}: ✅ {ok} · ➖ {mi} · ❌ {w} · own findings — {a}',
    '❌ без причины: {n} — причина нужна, чтобы понять, что исправлять в MINT.':
        '❌ without a reason: {n} — the reason shows what to fix in MINT.',
    '➡️ К неразмеченным':
        '➡️ To unmarked',
    'Страница (из {n})':
        'Page (of {n})',
    'Word недоступен: {e}':
        'Word is unavailable: {e}',
    'Замечания_{v}.docx':
        'Findings_{v}.docx',
    'Проверенный документ, в котором ваши замечания стоят примечаниями Word.':
        'The reviewed document with your findings as Word comments.',
    '📥 Скачать документ (.docx)':
        '📥 Download the document (.docx)',
    'Замечания_эксперта_{v}.docx':
        'Expert_findings_{v}.docx',
    'Отметки изменились — соберите документ заново.':
        'The marks have changed — build the document again.',
    'Разбор не сохранён на диск: {e}':
        'The assessment is not saved to disk: {e}',
    'копия документа не найдена в папке аудита':
        'no copy of the document in the review folder',
    'Документ не собран: {e}':
        'The document is not built: {e}',
    'Причина: —':
        'Reason: —',
    ' · разобрано {m} из {n}':
        ' · assessed {m} of {n}',
    '{t} · {f} · {m} · замечаний {n}':
        '{t} · {f} · {m} · findings {n}',
    'Аудит не найден: {v}':
        'Review not found: {v}',
    '📂 Мои аудиты':
        '📂 Saved reviews',
    'Каждый аудит сохраняется на этом компьютере ({p}): заключение, лог, документ с замечаниями и разбор эксперта. Откройте аудит, чтобы продолжить разбор замечаний.':
        'Every review is saved on this computer ({p}): the report, the log, the document with findings and the expert assessment. Open a review to continue assessing its findings.',
    'Аудит':
        'Review',
    '**📤 Все разборы для улучшения MINT** — аудитов с разбором: {n}':
        '**📤 All assessments for improving MINT** — reviews with marks: {n}',
    '📤 Собрать разборы':
        '📤 Collect the assessments',
    'Сводка по файлам разборов — tools/review_stats.py. С текстами в файле есть цитаты документов: передавайте его только туда, куда можно передавать сами документы.':
        'Summary of assessment files — tools/review_stats.py. With texts, the file contains quotes from documents: send it only where the documents themselves may be sent.',
    'Открыт сохранённый аудит: {f}.':
        'A saved review is open: {f}.',
    'Аудит не сохранён в «📂 Мои аудиты»: {e}':
        'The review is not saved to "📂 Saved reviews": {e}',
    'Сохранённых аудитов пока нет.':
        'No saved reviews yet.',
    '📂 Открыть':
        '📂 Open',
    'Да, удалить':
        'Yes, delete',
    '🗑️ Удалить аудит':
        '🗑️ Delete the review',
    'Только виды проверок, критичность, отметки и причины — без текстов замечаний, цитат, разделов, комментариев и имени файла.':
        'Only check kinds, severity, marks and reasons — no finding texts, quotes, sections, comments or file name.',
    '📥 Скачать разборы ({n}, .jsonl)':
        '📥 Download the assessments ({n}, .jsonl)',
    'найдены, но сняты вручную: {v}':
        'found but removed by hand: {v}',
}
