"""Unit-тесты: чтение .env (кодировки, кавычки, пустые системные переменные), описания ошибок подключения,
правила своего словаря, нормы по «особому вниманию».

Запуск из корня проекта:  python tests/test_env.py
"""
import http.server
import os
import shutil
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402

work = harness.make_project(prefix="mint_env_")
m = harness.load_mint(work, include_ui=True)
check_ = harness.Checker()


def check(name, cond, extra=""):
    check_(cond, name, extra)


for k in ("LLM_API_URL","EMBED_API_URL","LLM_API_KEY","_MINT_DOTENV_KEYS","LLM_MODEL"):
    os.environ.pop(k, None)
os.chdir(work)
body = ('# Комментарий по-русски\nexport LLM_API_URL="https://llm.corp/v1"\nEMBED_API_URL = https://llm.corp/v1/embeddings  # эмбеддинги\n'
        "LLM_API_KEY='sk-123 # не комментарий'\nLLM_MODEL=qwen3\nCA_BUNDLE_PATH=\n")
for label, data in [("UTF-8", body.encode("utf-8")), ("UTF-8 с BOM", b"\xef\xbb\xbf" + body.encode("utf-8")),
                    ("Windows-1251", body.encode("cp1251"))]:
    for parser in ("dotenv", "встроенный"):
        for k in ("LLM_API_URL","EMBED_API_URL","LLM_API_KEY","_MINT_DOTENV_KEYS","LLM_MODEL"):
            os.environ.pop(k, None)
        saved = m.dotenv_values
        if parser == "встроенный":
            m.dotenv_values = None
        (work / ".env").write_bytes(data)
        cfg, notes = m.load_settings()
        m.dotenv_values = saved
        check(f"{label}, {parser}: адреса", cfg.llm_url == "https://llm.corp/v1" and cfg.embed_url == "https://llm.corp/v1/embeddings",
              f"{cfg.llm_url!r} {cfg.embed_url!r}")
        check(f"{label}, {parser}: ключ в кавычках с #", cfg.llm_api_key == "sk-123 # не комментарий", repr(cfg.llm_api_key))
        check(f"{label}, {parser}: пустой CA не затёр умолчание", cfg.ca_bundle == "/etc/ssl/certs/ca-certificates.crt")
        check(f"{label}, {parser}: env_files заполнен", str((work / '.env').resolve()) in cfg.env_files, cfg.env_files)
        check(f"{label}, {parser}: проблем нет", m.check_settings(cfg) == [])

# пустая системная переменная не перекрывает .env, непустая — перекрывает
for k in ("LLM_API_URL","EMBED_API_URL","LLM_API_KEY","_MINT_DOTENV_KEYS"):
    os.environ.pop(k, None)
os.environ["LLM_API_URL"] = ""
os.environ["EMBED_API_URL"] = "https://system/v1/embeddings"
(work / ".env").write_text(body, encoding="utf-8")
cfg, _ = m.load_settings()
check("пустая системная LLM_API_URL → берётся из .env", cfg.llm_url == "https://llm.corp/v1", cfg.llm_url)
check("непустая системная EMBED_API_URL важнее .env", cfg.embed_url == "https://system/v1/embeddings", cfg.embed_url)

# .env отсутствует
for k in ("LLM_API_URL","EMBED_API_URL","LLM_API_KEY","_MINT_DOTENV_KEYS"):
    os.environ.pop(k, None)
(work / ".env").unlink()
cfg, _ = m.load_settings()
check("нет .env → env_files пуст и есть проблемы", cfg.env_files == "" and len(m.check_settings(cfg)) == 2)

# причины сетевых ошибок
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        code = 401 if "auth" in self.path else (404 if "nf" in self.path else 200)
        self.send_response(code); self.end_headers()
        self.wfile.write(b"<html>not json</html>" if code == 200 else b"")
    def log_message(self, *a): pass
srv = http.server.HTTPServer(("127.0.0.1", 0), H); port = srv.server_port
threading.Thread(target=srv.serve_forever, daemon=True).start()
cfg = m.Settings(llm_url=f"http://127.0.0.1:{port}/auth/v1")
errs = []; m._fetch_models_info(f"http://127.0.0.1:{port}/auth/v1/models", "", cfg, errors=errs)
check("HTTP 401 → подсказка про ключ", errs and "ключ" in errs[0], errs)
errs = []; m._fetch_models_info(f"http://127.0.0.1:{port}/nf/v1/models", "", cfg, errors=errs)
check("HTTP 404 → подсказка про адрес", errs and "адрес" in errs[0], errs)
errs = []; m._fetch_models_info(f"http://127.0.0.1:{port}/ok/v1/models", "", cfg, errors=errs)
check("не JSON → подсказка", errs and "JSON" in errs[0], errs)
errs = []; m._fetch_models_info("http://127.0.0.1:1/v1/models", "", cfg, errors=errs)
check("нет соединения → подсказка", errs and "нет соединения" in errs[0], errs)
info = m.detect_server_info(m.Settings(llm_url=f"http://127.0.0.1:{port}/auth/v1"))
check("detect_server_info возвращает llm_error", "ключ" in info.get("llm_error", ""), info)
import requests
check("SSL → подсказка про CA_BUNDLE_PATH", "CA_BUNDLE_PATH" in m.describe_request_error(requests.exceptions.SSLError("x"), "https://h/v1"))
a = m._conn_sig(m.Settings(llm_api_key="a")); b = m._conn_sig(m.Settings(llm_api_key="b"))
check("отпечаток подключения меняется при смене ключа", a != b)
srv.shutdown()

# словарь: удаление ошибочной записи, Windows-1251, инструкция-ключ игнорируется
g = work / "glossary_test.json"
g.write_bytes('{"_как_пользоваться": "текст", "СЗИ": "средства защиты", "АБВ": "", "ЦОД": null}'.encode("cp1251"))
man = m.load_manual_glossary(g)
check("glossary.json в Windows-1251 читается", man.get("СЗИ") == "средства защиты", man)
gl = m.Glossary(man, {"АБВ": "ошибочная расшифровка", "ЦОД": "центр обработки данных", "СХД": "система хранения данных"})
check("пустое значение убирает запись из документов", "АБВ" not in gl.entries and "ЦОД" not in gl.entries, gl.entries)
check("остальные записи из документов остаются", gl.entries.get("СХД") == "система хранения данных")
check("счётчики: свои 1, из документов 1, убрано 2", (gl.manual_count, gl.auto_count, gl.removed_count) == (1, 1, 2),
      (gl.manual_count, gl.auto_count, gl.removed_count))
check("ключи на «_» игнорируются", "_как_пользоваться" not in gl.entries)
# нормы по «особому вниманию»: первыми, без дублей, в пределах лимита; низкая уверенность — не добавляются
orig = m.search_parent_child
def fake(query, cfg, k_neighbors=5, return_items=False, glossary=None, diagnostics=None, **kw):
    if diagnostics is not None:
        diagnostics["low_conf"] = "шум" in query
    mk = lambda i: {"id": i, "block": f"=== ИСТОЧНИК: {i} ===\n" + "т" * 2500, "short": f"📄 {i}", "label": i}
    if "особ" in query or "шум" in query:
        return [mk("F1"), mk("S1")], ["F1", "S1"]
    return [mk("S1"), mk("S2"), mk("S3")], ["S1", "S2", "S3"]
m.search_parent_child = fake
cfgN = m.Settings(audit_context_max_chars=9000)
fi = m.special_focus_norms("особое: шифрование", cfgN)
check("нормы по особому вниманию найдены", [x["id"] for x in fi] == ["F1", "S1"], fi)
check("при низкой уверенности не добавляются", m.special_focus_norms("шум", cfgN) == [])
txt, shorts = m.build_norms_context("раздел", cfgN, 5, extra_items=fi)
check("нормы по особому вниманию — первыми, без дублей, в пределах лимита",
      shorts == ["📄 F1", "📄 S1", "📄 S2"], shorts)
m.search_parent_child = orig
os.chdir(harness.ROOT)
shutil.rmtree(work, ignore_errors=True)
check_.finish()
