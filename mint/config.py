"""Настройки: .env (подключения), config.yaml (параметры), значения по умолчанию."""

import io
import json
import logging
import os
import re
from dataclasses import dataclass, fields
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

try:
    from dotenv import dotenv_values
except ImportError:
    dotenv_values = None

from .i18n import tr

logger = logging.getLogger("MINT")


APP_DIR = Path(__file__).resolve().parent.parent   # папка проекта: .env, config.yaml, glossary.json


# Поля, которые задаются только через окружение / .env (в config.yaml игнорируются).
ENV_FIELDS = {
    "llm_url": ("LLM_API_URL",),
    "embed_url": ("EMBED_API_URL",),
    "rerank_url": ("RERANK_API_URL",),
    "llm_api_key": ("LLM_API_KEY",),
    "embed_api_key": ("EMBED_API_KEY",),
    "rerank_api_key": ("RERANK_API_KEY",),
    "llm_model": ("LLM_MODEL", "DEFAULT_LLM_MODEL"),
    "embed_model": ("EMBED_MODEL",),
    "rerank_model": ("RERANK_MODEL",),
    "ca_bundle": ("CA_BUNDLE_PATH",),
    "ssl_insecure": ("SSL_INSECURE",),
    "kb_dir": ("KB_DIR",),
    "log_dir": ("LOG_DIR",),
    "glossary_path": ("GLOSSARY_PATH",),
    "prompts_path": ("PROMPTS_PATH",),
}


# Поля, которые можно задать и в config.yaml, и в окружении / .env (окружение важнее): их удобно менять
# вместе с подключением к шлюзу.
ENV_OPTIONAL = {
    "llm_no_reasoning": "LLM_NO_REASONING",
    "llm_extra_body": "LLM_EXTRA_BODY",
}


# Служебные поля: заполняются самим MINT, в config.yaml не задаются.
INTERNAL_FIELDS = {"config_path", "llm_context_known", "embed_input_max_chars", "explicit_fields",
                   "embed_prefix_source", "env_files", "env_parser"}


@dataclass(frozen=True)
class Settings:
    # ---------- Подключения (.env) ----------
    llm_url: str = ""                 # база OpenAI-совместимого API: https://host/v1
    embed_url: str = ""               # полный адрес эндпоинта эмбеддингов: https://host/v1/embeddings
    rerank_url: str = ""              # полный адрес реранкера: https://host/v1/rerank (пусто — без реранкера)
    llm_api_key: str = ""
    embed_api_key: str = ""           # пусто — используется llm_api_key
    rerank_api_key: str = ""          # пусто — используется llm_api_key
    llm_model: str = ""               # модель по умолчанию; пусто — первая из списка сервера
    embed_model: str = "qwen3-embedding-4b"
    rerank_model: str = "bge-reranker-v2-m3"
    ca_bundle: str = "/etc/ssl/certs/ca-certificates.crt"
    ssl_insecure: bool = False
    kb_dir: str = "~/knowledge_base"
    log_dir: str = "~/mint_logs"
    glossary_path: str = ""
    prompts_path: str = ""            # свои правки промптов; пусто — prompts.yaml рядом с программой

    # ---------- Лимиты моделей (0 — определить у сервера или взять типовое значение) ----------
    llm_context_tokens: int = 0       # окно контекста LLM
    embed_max_tokens: int = 0         # максимальная длина входа модели эмбеддингов
    rerank_max_tokens: int = 0        # максимальная длина пары «запрос + документ» у реранкера
    chars_per_token: float = 0.0      # символов текста на токен; 0 — 2.5 или измерить в панели (на языке базы)
    embed_query_prefix: str = ""      # инструкция перед текстом ЗАПРОСА; не задано — по имени модели
    embed_doc_prefix: str = ""        # префикс перед текстом ДОКУМЕНТА (e5: "passage: "); меняет индекс

    # ---------- Профиль ----------
    profile: str = "general"          # набор промптов: general — любые документы; architecture — архитектура и
                                      # ИТ-решения (промпты MINT до появления профилей, слово в слово)

    # ---------- Языковая модель ----------
    temperature: float = 0.1
    max_tokens: int = 1500            # максимальная длина ответа модели
    llm_timeout: int = 90             # сек на одну попытку
    llm_retries: int = 2              # попыток при таймауте и 502/503/504; на 429 — не меньше 4 (services.RATE_LIMIT_ATTEMPTS)
    llm_no_reasoning: bool = False    # выключить рассуждения модели перед ответом (стандартный параметр vLLM, SGLang)
    llm_extra_body: str = ""          # свои параметры запроса к LLM, JSON-объект: {"top_p": 0.9}; config.yaml или .env
    llm_stream: bool = True           # аудит: ответ потоком — MINT обрывает слишком длинный или зациклившийся ответ
    request_timeout: int = 120        # сек на запрос к реранкеру

    # ---------- Индексация (рассчитываются по лимитам моделей) ----------
    parent_size: int = 2500
    parent_overlap: int = 300
    child_size: int = 400
    child_overlap: int = 150
    embed_batch_size: int = 32

    # ---------- Поиск ----------
    top_k: int = 0                    # 0 — автоматически (4 или 5 по размеру базы)
    initial_k: int = 50
    bm25_top_k: int = 20
    rerank_top_k: int = 16
    rrf_constant: int = 60
    weight_dense: float = 1.0
    weight_bm25: float = 1.0
    weight_rerank: float = 0.7
    smart_truncate_chars: int = 3500
    max_table_parts: int = 2
    use_multi_query: bool = False
    multi_query_alt_weight: float = 0.85
    max_query_chars: int = 24000
    cascade_split_chars: int = 20000

    # ---------- Реранкер ----------
    rerank_max_docs: int = 10         # документов в одном запросе к реранкеру
    rerank_query_max_chars: int = 1500
    rerank_doc_max_chars: int = 800   # самый релевантный фрагмент документа (вместе с именем файла и разделом)
    rerank_char_budget: int = 9000    # символов в одном запросе; не поместившееся уходит следующим запросом
    rerank_with_meta: bool = True
    min_rerank_score: float = 0.15

    # ---------- Сигнал «уверенность низкая» и вывод ----------
    low_conf_rerank: float = 0.30
    low_conf_lexical: float = 0.50
    low_conf_agree_top: int = 5
    show_source_details: bool = True

    # ---------- Чат ----------
    chat_history_turns: int = 2       # сколько предыдущих пар «вопрос — ответ» учитывать; 0 — без истории

    # ---------- Глоссарий ----------
    glossary_auto: bool = True        # собирать сокращения из загруженных документов
    glossary_in_context: bool = True  # передавать модели справочник найденных сокращений
    glossary_max_entries: int = 20

    # ---------- Аудит документа ----------
    audit_map_size: int = 4500
    use_self_critique: bool = True
    audit_query_chars: int = 2000
    audit_context_max_chars: int = 9000
    audit_full_document: bool = True      # весь документ в каждой проверке раздела, если помещается в окно модели
    audit_merge_duplicates: bool = True   # сведение повторов моделью в конце аудита (+1 вызов LLM)
    audit_known_abbreviations: str = ""   # общеизвестные сокращения через запятую — проверка сокращений их не отмечает
    audit_deep: bool = True               # глубокая проверка: процесс по шагам, противоречия, цифры, опечатки
    audit_deep_max_calls: int = 60        # не больше стольких вопросов модели в глубокой проверке (0 — без лимита)
    audit_parallel: int = 3               # запросов к модели одновременно: разделы, вопросы глубокой проверки, пункты
    audit_pinned_max_chars: int = 20000   # правила экспертов и карточки систем на один запрос аудита (сверх норм поиска)
    audit_systems: bool = True            # по каждой упомянутой системе с карточкой: что документ от неё требует
    audit_basis_docs: bool = True         # документы-основания (ссылки на титуле и в «Ссылочных документах») —
                                          # найти в базе и давать их фрагменты в каждую проверку раздела
    audit_basis_max_chars: int = 8000     # фрагменты документов-оснований на один запрос аудита (сверх норм поиска)
    audit_passes: int = 1                 # проходов проверки разделов и глубокой проверки; 2–3 — находки проходов
                                          # объединяются: случайные пропуски реже, найденное несколько раз — выше
    audit_summary_max: int = 12           # «Главное» в начале заключения: не больше стольких замечаний (0 — без блока)
    audit_reasoning: bool = False         # аудит с рассуждениями модели (поверх llm_no_reasoning), таймаут ≥ 300 с

    # ---------- Контроль исправлений ----------
    review_top_sections: int = 3
    review_context_max_chars: int = 12000
    section_embed_chars: int = 4000

    # ---------- Служебные ----------
    config_path: str = ""
    llm_context_known: bool = False
    embed_input_max_chars: int = 0
    explicit_fields: frozenset = frozenset()
    embed_prefix_source: str = ""
    env_files: str = ""               # прочитанные файлы .env (через «; »), пусто — не найдены
    env_parser: str = ""              # чем прочитан .env: python-dotenv или встроенный разбор

    # ---------- Производные значения ----------
    @property
    def llm_base(self) -> str:
        return (self.llm_url or "").rstrip("/")

    @property
    def embed_key(self) -> str:
        return self.embed_api_key or self.llm_api_key

    @property
    def rerank_key(self) -> str:
        return self.rerank_api_key or self.llm_api_key

    @property
    def rerank_enabled(self) -> bool:
        return bool(self.rerank_url)

    @property
    def tls_verify(self):
        """False — проверка отключена; путь — свой CA-сертификат; True — системные сертификаты."""
        if self.ssl_insecure:
            return False
        if self.ca_bundle and os.path.isfile(self.ca_bundle):
            return self.ca_bundle
        return True

    @property
    def kb_path(self) -> Path:
        return Path(os.path.expanduser(self.kb_dir))

    @property
    def log_path(self) -> Path:
        return Path(os.path.expanduser(self.log_dir))

    @property
    def glossary_file(self) -> Path:
        """glossary.json рядом с программой; для совместимости с v17 — в папке базы, если он лежит там."""
        if self.glossary_path:
            return Path(os.path.expanduser(self.glossary_path))
        local = APP_DIR / "glossary.json"
        legacy = self.kb_path / "glossary.json"
        if not local.exists() and legacy.exists():
            return legacy
        return local

    @property
    def rrf_weights(self) -> dict:
        return {"dense": self.weight_dense, "bm25": self.weight_bm25, "rerank": self.weight_rerank}


SETTING_NAMES = {f.name for f in fields(Settings)}

DEFAULTS = Settings()


def _coerce(value, default):
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "on", "да")
    if isinstance(default, int):
        return int(float(value))
    if isinstance(default, float):
        return float(value)
    return "" if value is None else str(value)


def env_file_candidates():
    """Где MINT ищет .env: рядом с программой и в папке, из которой её запустили."""
    return [APP_DIR / ".env", Path.cwd() / ".env"]


def _read_text_any(path):
    """Текст файла в UTF-8 (с BOM или без) или Windows-1251 — так сохраняют Блокнот и Excel."""
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1251"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _parse_env_text(text):
    """Разбор .env без python-dotenv: КЛЮЧ=значение, # комментарии, export, значения в кавычках."""
    out = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        if s.startswith("export "):
            s = s[7:].lstrip()
        k, v = s.split("=", 1)
        k, v = k.strip(), v.strip()
        if v[:1] in ("'", '"'):
            end = v.find(v[0], 1)
            v = v[1:end] if end > 0 else v[1:]
        else:
            v = re.split(r"\s+#", v, maxsplit=1)[0].strip()
        if k:
            out[k] = v
    return out


def _load_env_files():
    """Читает .env рядом с программой и в текущей папке. Переменные, заданные в системе, важнее .env;
    переменные, пришедшие из .env, обновляются при его изменении (без перезапуска MINT).
    Возвращает (прочитанные файлы, чем прочитаны)."""
    owned = set(filter(None, os.environ.get("_MINT_DOTENV_KEYS", "").split(",")))
    seen, read, parser = set(), [], ""
    for p in env_file_candidates():
        if not p.is_file():
            continue
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        try:
            text = _read_text_any(p)
        except OSError as e:
            logger.warning(f".env не прочитан ({p}): {e}")
            continue
        if dotenv_values is not None:
            values, parser = dotenv_values(stream=io.StringIO(text)), "python-dotenv"
        else:
            values, parser = _parse_env_text(text), tr("встроенный разбор (python-dotenv не установлен)")
        for k, v in values.items():
            k = (k or "").lstrip("\ufeff").strip()
            if not k or v is None:
                continue
            if not os.environ.get(k, "").strip() or k in owned:
                os.environ[k] = v
                owned.add(k)
        read.append(str(rp))
    os.environ["_MINT_DOTENV_KEYS"] = ",".join(sorted(owned))
    return read, parser


def prompts_file_path() -> Path:
    """Свои правки промптов: PROMPTS_PATH (из окружения или .env) или prompts.yaml рядом с программой."""
    p = os.environ.get("PROMPTS_PATH", "").strip()
    if not p:
        return APP_DIR / "prompts.yaml"
    path = Path(os.path.expanduser(p))
    return path if path.is_absolute() else APP_DIR / path


def config_file_path() -> Path:
    """MINT_CONFIG или config.yaml рядом с программой; относительный путь — от папки программы."""
    p = os.environ.get("MINT_CONFIG", "").strip()
    if not p:
        return APP_DIR / "config.yaml"
    path = Path(os.path.expanduser(p))
    return path if path.is_absolute() else APP_DIR / path


def load_settings():
    """Возвращает (Settings, notes): notes — предупреждения о проблемах в config.yaml."""
    env_files, env_parser = _load_env_files()
    values, notes, explicit = {}, [], set()

    path = config_file_path()
    if path.is_file():
        if yaml is None:
            notes.append(tr("config.yaml не прочитан: не установлен PyYAML (pip install pyyaml)."))
        else:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = yaml.safe_load(f) or {}
            except Exception as e:
                raw = {}
                notes.append(tr("config.yaml не прочитан ({v}) — используются значения по умолчанию.", v=str(e)[:150]))
            if not isinstance(raw, dict):
                notes.append(tr("config.yaml должен содержать параметры вида «имя: значение» — файл пропущен."))
                raw = {}
            flat = {}
            for k, v in raw.items():
                if isinstance(v, dict):      # группы (models:, search:, ...) — только для удобства чтения
                    flat.update(v)
                else:
                    flat[k] = v
            for k, v in flat.items():
                if k == "llm_extra_body" and isinstance(v, dict):     # в YAML удобнее писать словарём
                    v = json.dumps(v, ensure_ascii=False)
                if k == "audit_known_abbreviations" and isinstance(v, (list, tuple)):     # или списком
                    v = ", ".join(str(x) for x in v)
                if k in ENV_FIELDS:
                    notes.append(tr("Параметр «{k}» в config.yaml не используется: подключения задаются в .env.", k=k))
                elif k not in SETTING_NAMES or k in INTERNAL_FIELDS:
                    notes.append(tr("Неизвестный параметр «{k}» в config.yaml — пропущен.", k=k))
                elif v is None:
                    continue
                else:
                    try:
                        values[k] = _coerce(v, getattr(DEFAULTS, k))
                        explicit.add(k)
                    except (TypeError, ValueError):
                        notes.append(tr("Параметр «{k}»: неверное значение {v!r} — оставлено {v2!r}.", k=k, v=v, v2=getattr(DEFAULTS, k)))

    for name, env_names in ENV_FIELDS.items():
        for env in env_names:
            val = os.environ.get(env)
            if val is not None and val.strip():
                values[name] = _coerce(val.strip(), getattr(DEFAULTS, name))
                break

    for name, env in ENV_OPTIONAL.items():
        val = os.environ.get(env)
        if val is not None and val.strip():
            values[name] = _coerce(val.strip(), getattr(DEFAULTS, name))
            explicit.add(name)

    values["config_path"] = str(path) if path.is_file() else ""
    values["explicit_fields"] = frozenset(explicit)
    values["env_files"] = "; ".join(env_files)
    values["env_parser"] = env_parser
    return Settings(**values), notes


def check_settings(cfg: Settings):
    """Проблемы конфигурации для показа пользователю: список (уровень, текст)."""
    out = []
    if not cfg.llm_url:
        out.append(("error", tr("Не задан адрес языковой модели — укажите LLM_API_URL в файле .env.")))
    if not cfg.embed_url:
        out.append(("error", tr("Не задан адрес сервиса эмбеддингов — укажите EMBED_API_URL в файле .env.")))
    if extra_body_error(cfg):
        out.append(("warning", extra_body_error(cfg)))
    from .prompts import PROFILES      # здесь, а не в начале модуля: prompts сам читает config
    if cfg.profile not in PROFILES:
        out.append(("warning", tr("Неизвестный профиль profile = «{v}» — используется «general». Профили: {names}.",
                                  v=cfg.profile, names=", ".join(PROFILES))))
    return out


def extra_body(cfg):
    """Свои параметры запроса к LLM (llm_extra_body) словарём; неверный JSON — пустой словарь."""
    raw = (cfg.llm_extra_body or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def extra_body_error(cfg):
    """Что не так с llm_extra_body (пустая строка — всё в порядке)."""
    raw = (cfg.llm_extra_body or "").strip()
    if not raw:
        return ""
    try:
        data = json.loads(raw)
    except ValueError as e:
        return tr("llm_extra_body / LLM_EXTRA_BODY — не JSON ({e}): параметры не отправляются.", e=str(e)[:80])
    if not isinstance(data, dict):
        return tr("llm_extra_body / LLM_EXTRA_BODY должен быть объектом JSON — параметры не отправляются.")
    reserved = sorted(set(data) & {"model", "messages", "stream"})
    if reserved:
        return tr("llm_extra_body: поля {v} задаёт сам MINT — они не отправляются.", v=", ".join(reserved))
    return ""


# Пользователь задаёт (или MINT узнаёт у сервера) окно LLM, вход моделей эмбеддингов и реранкера.
# Из них считаются ПОТОЛКИ для размеров фрагментов и объёмов контекста. Значение параметра =
# min(значение по умолчанию, потолок): большое окно не раздувает фрагменты (длинный контекст добавляет
# шум, а не точность), а маленькое — уменьшает их, чтобы ничего не обрезалось и не падало.

FALLBACK_LIMITS = {
    "llm_context_tokens": 32768,
    "embed_max_tokens": 8192,
    "rerank_max_tokens": 8192,
    "chars_per_token": 2.5,
}
