"""Журнал MINT: файл с ротацией и консоль."""

import logging
from logging.handlers import RotatingFileHandler

from .config import Settings

logger = logging.getLogger("MINT")


def setup_logging(cfg: Settings):
    """Логгер MINT: файл с ротацией + консоль. Настраивается один раз на процесс (Streamlit перезапускает
    скрипт при каждом действии, а логгер живёт дольше — повторно файлы не открываются)."""
    if any(getattr(h, "_mint_handler", False) for h in logger.handlers):
        return logger
    fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] [MINT_CORE]: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    logger.setLevel(logging.INFO)
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()
    try:
        cfg.log_path.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(cfg.log_path / "mint_system.log", maxBytes=10 * 1024 * 1024,
                                 backupCount=5, encoding="utf-8")
        fh.setFormatter(fmt)
        fh._mint_handler = True
        logger.addHandler(fh)
    except OSError as e:
        print(f"MINT: не удалось открыть файл лога ({e}); пишу только в консоль.")
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    ch._mint_handler = True
    logger.addHandler(ch)
    logger.propagate = False
    if cfg.tls_verify is False:
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        except Exception:
            pass
        logger.warning("TLS-проверка отключена (SSL_INSECURE=1). Используйте только во внутренней сети.")
    return logger
