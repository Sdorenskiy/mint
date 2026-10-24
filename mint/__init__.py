"""MINT — интеллектуальная RAG-система: ответы по базе знаний, аудит документов, контроль исправлений.

Ядро (всё, кроме mint.ui) не зависит от Streamlit и может использоваться из скриптов. Сценарии целиком:

    from mint.chat import answer_question            # ответ чата: поиск → модель → проверка ссылок
    from mint.audit import run_audit                 # аудит документа: разделы → замечания → заключение
    from mint.review import verify_remarks           # контроль исправления замечаний в новой редакции

Модули по слоям (стрелка — «использует»):
    config, version, cache, stemmer, text, prompts     — основа без внешних вызовов (тексты промптов —
                                                         mint/prompts/ru.yaml и en.yaml)
    services → config                                    — HTTP: LLM, эмбеддинги, реранкер
    limits → config, services                            — окна моделей и расчёт параметров
    bm25 → stemmer;  glossary → bm25                     — лексический поиск и сокращения
    parsing → cache, text                                — разбор .docx (Docling)
    kb → parsing, services, bm25, glossary               — база знаний: индексация и загрузка
    passages → bm25, text                                — склейка соседних фрагментов, окно вокруг найденного
    search → kb, bm25, services, passages                — гибридный поиск parent/child
    citations → bm25                                     — проверка ссылок [Источник: …] в ответе чата
    audit, review, chat → search, services, prompts      — сценарии (chat → citations: проверка ссылок)
    evaluation → search, chat, citations, kb             — проверка качества: вопросы, прогон, метрики
    expert_review → audit;  audit_store → expert_review  — разбор замечаний экспертом, сохранённые аудиты
    ui                                                   — интерфейс Streamlit
"""

from .version import MINT_VERSION

__all__ = ["MINT_VERSION"]
