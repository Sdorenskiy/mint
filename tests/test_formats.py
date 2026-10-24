"""Форматы документов: .pdf без моделей (закладки, оглавление, слайды, шрифт; колонтитулы, штамп, таблицы;
скан и испорченный текст), .md, .txt — разбор, Markdown для аудита и загрузка в базу знаний.

Запуск из корня проекта:  python tests/test_formats.py
Для PDF нужны pdfplumber и reportlab (тестовые PDF собираются на лету); без них проверяются .md и .txt.
"""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402
import mock_server  # noqa: E402
import pdf_fixtures as fx  # noqa: E402

W = harness.make_project(prefix="mint_formats_")
srv = mock_server.start()
BASE = f"http://127.0.0.1:{srv.server_address[1]}/v1"
os.environ.update({
    "LLM_API_URL": BASE, "EMBED_API_URL": BASE + "/embeddings", "RERANK_API_URL": "",
    "LLM_MODEL": "test-llm", "EMBED_MODEL": "emb-model", "KB_DIR": str(W / "kb"), "LOG_DIR": str(W / "logs"),
    "MINT_CONFIG": str(W / "none.yaml"), "GLOSSARY_PATH": str(W / "none.json"), "MINT_LANG": "ru",
})
os.chdir(W)
app = harness.load_mint(W, include_ui=False)
check = harness.Checker()


def unreadable(name, data):
    try:
        app.parse_document(name, data)
    except app.DocumentUnreadable as e:
        return str(e)
    return ""


print("1. [unit] Определение формата")
check([app.document_format(n) for n in ("a.DOCX", "b.pdf", "c.md", "d.TXT", "e.doc", "f")] ==
      ["docx", "pdf", "md", "txt", None, None], "расширения без учёта регистра; .doc и без расширения — нет")
check("не поддерживается" in unreadable("старый.doc", b"x"), "неизвестный формат — понятное сообщение")

print("2. [unit] Markdown")
md = """# Регламент АС «Учёт»

Вводный абзац со [ссылкой](http://wiki/x) и картинкой ![схема](img.png) и **жирным**.

## 1. Общие положения
Первая строка абзаца
и его продолжение.

Подраздел без решёток
---------------------

| Показатель | Значение |
|---|---|
| RTO | 4 часа |

```
код # не заголовок
```
"""
units, tables = app.parse_markdown(md)
heads = [(u["level"], u["text"]) for u in units if u["level"]]
check(heads == [(1, "Регламент АС «Учёт»"), (2, "1. Общие положения"), (2, "Подраздел без решёток")],
      f"заголовки # и подчёркнутые: {heads}")
paras = [u["text"] for u in units if not u["level"]]
check("Вводный абзац со ссылкой (http://wiki/x) и картинкой схема и жирным." in paras
      and "Первая строка абзаца и его продолжение." in paras, f"абзацы и разметка внутри строки: {paras[:2]}")
check(any("код # не заголовок" in p for p in paras), "блок кода — текст, а не заголовок")
check(len(tables) == 1 and "| RTO | 4 часа |" in tables[0]["md"]
      and tables[0]["path"] == "Регламент АС «Учёт» → Подраздел без решёток", f"таблица с путём заголовков: {tables}")
r = app.parse_document("doc.md", md.encode("utf-8"))
check(r["info"]["structure"] == "markdown" and r["info"]["headings"] == 3 and not r["pages_real"], f"info: {r['info']}")

print("3. [unit] Обычный текст (.txt)")
txt = ("РЕГЛАМЕНТ ЭКСПЛУАТАЦИИ\n\n1. Общие положения\nДокумент определяет порядок эксплуатации системы и обязанности "
       "администраторов.\n\n1.1 Шифрование\n\nПередача данных выполняется с шифро-\nванием по ГОСТ.\n\n"
       "Это обычный абзац без точки в конце\n")
units, _ = app.parse_plain_text(txt)
heads = [(u["level"], u["text"]) for u in units if u["level"]]
check(heads == [(1, "РЕГЛАМЕНТ ЭКСПЛУАТАЦИИ"), (1, "1. Общие положения"), (2, "1.1 Шифрование")],
      f"заголовки: ЗАГЛАВНЫЕ и нумерованные: {heads}")
paras = [u["text"] for u in units if not u["level"]]
check("Передача данных выполняется с шифрованием по ГОСТ." in paras and units[-1]["path"].endswith("1.1 Шифрование"),
      f"абзацы склеены, перенос по слогам убран: {paras}")
r = app.parse_document("doc.txt", txt.encode("cp1251"))
check(r["info"]["structure"] == "numbering" and r["units"][0]["text"] == "РЕГЛАМЕНТ ЭКСПЛУАТАЦИИ",
      "файл в Windows-1251 читается")
lines_only = "\n".join(f"Строка номер {i} обычного журнала событий." for i in range(30))
check(len(app.parse_plain_text(lines_only)[0]) == 30, "текст без пустых строк — абзац на каждую строку")
check(app.decode_text("тест".encode("utf-16")) == "тест" and app.decode_text("﻿тест".encode("utf-8")) == "тест",
      "UTF-16 и UTF-8 с BOM")

why = fx.available()
if why:
    print(f"::warning title=PDF не проверены::{why}")
    print(f"4–7. PDF пропущены: {why}")
else:
    print("4. [unit] PDF: закладки, колонтитулы, перенос, таблица, заголовок в две строки")
    check(app._clean_rows([["", "Термин", "", "Определение"], ["AD", None, "Active Directory", None]]) ==
          [["Термин", "Определение"], ["AD", "Active Directory"]]
          and app._clean_rows([["a", "b"], ["", "x"]]) == [["a", "b"], ["", "x"]],
          "таблица: объединённые ячейки шапки не сдвигают колонки, обычные колонки не сливаются")
    r = app.parse_document("Регламент.pdf", fx.outline_pdf())
    info, units, tables = r["info"], r["units"], r["tables"]
    heads = [(u["level"], u["text"], u["page"]) for u in units if u["level"]]
    check(info["structure"] == "outline" and info["pages"] == 3 and r["pages_real"], f"info: {info}")
    check(heads == [(1, "1. Общие положения", 1),
                    (2, "1.1 Назначение документа и область его применения для всех подсистем автоматизированной "
                        "системы", 1),
                    (1, "2. Требования к информационной безопасности", 2), (1, "3. Показатели надёжности", 3)],
          f"заголовки из закладок с уровнями и страницами: {heads}")
    texts = [u["text"] for u in units]
    check(not any(fx.HEADER in t for t in texts) and not any(t.strip().isdigit() for t in texts),
          "колонтитул и номера страниц убраны")
    check(not any(t == "подсистем автоматизированной системы" for t in texts),
          "вторая строка заголовка не стала абзацем")
    body = " ".join(texts)
    check("с шифрованием по ГОСТ Р 34.12-2015" in body, "перенос по слогам убран, «34.12-2015» не тронут")
    check(len(tables) == 1 and "| RTO | 4 часа | Служба эксплуатации |" in tables[0]["md"]
          and tables[0]["path"] == "2. Требования к информационной безопасности" and tables[0]["page"] == 2,
          f"таблица с сеткой — Markdown с путём и страницей: {tables}")
    check("Служба эксплуатации" not in body, "текст таблицы не повторяется в абзацах")
    rto = [u for u in units if "RTO" in u["text"] and not u["level"]]
    check(rto and rto[0]["path"] == "3. Показатели надёжности" and rto[0]["page"] == 3, "абзац знает раздел и страницу")
    md = app.document_to_markdown("Регламент.pdf", fx.outline_pdf())
    check(md.startswith("# 1. Общие положения") and md.index("| RTO |") > md.index("# 2. Требования")
          and md.index("| RTO |") < md.index("# 3. Показатели"), "Markdown для аудита: таблица на своём месте")
    check(len(app.split_into_sections(md, 200)) >= 3, "Markdown режется на разделы")

    print("5. [unit] PDF: страница «Содержание», штамп и поле ЕСКД, повёрнутый текст")
    r = app.parse_document("Руководство.pdf", fx.toc_pdf())
    heads = [(u["level"], u["text"], u["page"]) for u in r["units"] if u["level"]]
    check(r["info"]["structure"] == "toc" and heads == [(1, "1. Введение", 2), (1, "2. Технические характеристики", 2),
                                                         (2, "2.1 Габариты", 3), (1, "3. Монтаж", 4)],
          f"заголовки по оглавлению, уровни по нумерации: {r['info']['structure']}, {heads}")
    texts = " ".join(u["text"] for u in r["units"])
    check(not any(s in texts for s in ("Содержание", ".....", "Инв. № подл", "Лист № докум", "Подп. и дата")),
          f"оглавление, поле, штамп и повёрнутый текст не попали в текст: {texts[:200]}")
    check("Высота корпуса — 1U" in texts and next(u for u in r["units"] if "Высота" in u["text"])["path"]
          == "2. Технические характеристики → 2.1 Габариты", "абзац под своим заголовком")

    print("6. [unit] PDF: слайды и заголовки по шрифту")
    r = app.parse_document("Презентация.pdf", fx.slides_pdf())
    heads = [u["text"] for u in r["units"] if u["level"]]
    check(r["info"]["structure"] == "slides" and heads == [t for t, _ in fx.SLIDES],
          f"заголовки слайдов, без заглушки макета «Образец заголовка»: {heads}")
    check(any("Облачные решения" in u["text"] and u["path"] == "Проблемы и актуальные угрозы" for u in r["units"]),
          "пункт слайда — под заголовком слайда")
    r = app.parse_document("Буклет.pdf", fx.font_pdf())
    heads = [u["text"] for u in r["units"] if u["level"]]
    check(r["info"]["structure"] == "font" and heads == ["Описание продукта InfoBox", "Назначение", "Возможности"],
          f"заголовки по размеру шрифта: {heads}")

    print("7. [unit] PDF: скан и испорченный текст не индексируются")
    msg = unreadable("Скан.pdf", fx.scan_pdf())
    check("нет текстового слоя" in msg, f"скан — понятное сообщение: {msg[:80]}")
    check(app.text_quality("Рисунок 5 — запуск провайдера") == 0 and app.text_quality("Ɋɢɫɭɧɨɤ ± Ɂɚɩɭɫɤ") > 0.8
          and app.text_quality("(cid:586)(cid:610)(cid:619) (cid:3)") > 0.8, "признаки испорченной кодировки")
    real_quality = app.text_quality
    app.text_quality = lambda text: 1.0
    msg = unreadable("Печать.pdf", fx.outline_pdf())
    app.text_quality = real_quality
    check("повреждён" in msg and "Сохранить как PDF" in msg, f"испорченный текст — что делать: {msg[:80]}")

print("8. [интеграция] Загрузка в базу знаний: .pdf, .md, .txt; поиск; переиндексация; нечитаемый PDF")
cfg, _ = app.load_settings()
cfg, _ = app.resolve_settings(cfg, app.resolve_model_limits(cfg, {}, None, {}), {})
docs = {"Регламент.md": "# Регламент\n\n## Хранение журналов\n\nЖурналы событий безопасности хранятся не менее "
                        "трёх лет.\n".encode()}
docs["Памятка.txt"] = "1. Пароли\nПароль администратора меняется каждые 90 дней.\n".encode("cp1251")
if not why:
    docs["Регламент_АС.pdf"] = fx.outline_pdf()
for name, data in docs.items():
    ok, msg = app.process_and_add_to_kb(name, data, cfg)
    check(ok and "Структура:" in msg, f"{name}: загружен — {msg}")
manifest = app.read_manifest(cfg).get("documents") or {}
check(manifest.get("Регламент.md", {}).get("structure") == "markdown"
      and manifest.get("Памятка.txt", {}).get("format") == "txt", "в манифесте — формат и источник структуры")
items, srcs = app.search_parent_child("сколько хранятся журналы событий безопасности", cfg, k_neighbors=2,
                                      return_items=True)
check(items and items[0]["source"] == "Регламент.md" and "## Хранение журналов" in items[0]["block"],
      f"поиск находит фрагмент .md вместе с заголовком раздела: {[i['short'] for i in items]}")
if not why:
    check(manifest.get("Регламент_АС.pdf", {}).get("structure") == "outline", "PDF: структура из закладок")
    items, srcs = app.search_parent_child("время восстановления сервиса RTO", cfg, k_neighbors=3, return_items=True)
    hit = [i for i in items if i["source"] == "Регламент_АС.pdf" and "4 час" in i["block"]]
    check(hit and "# 3. Показатели надёжности" in hit[0]["block"], f"поиск по PDF с разделом: {[i['short'] for i in items]}")
    ok, msg = app.process_and_add_to_kb("Скан.pdf", fx.scan_pdf(), cfg)
    check(not ok and "нет текстового слоя" in msg and "Скан.pdf" not in app.list_kb_documents(cfg)[0],
          f"скан не попал в базу: {msg[:80]}")
results = app.reindex_documents(cfg)
check(results and all(ok for _, ok, _ in results) and {n for n, _, _ in results} == set(docs),
      f"переиндексация из сохранённых оригиналов: {[(n, ok) for n, ok, _ in results]}")

srv.shutdown()
os.chdir(harness.ROOT)
shutil.rmtree(W, ignore_errors=True)
check.finish()
