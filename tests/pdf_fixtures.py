"""Тестовые PDF для разбора без моделей (mint/pdfparse.py): собираются на лету через reportlab.

outline_pdf — закладки, колонтитул, номера страниц, перенос по слогам, таблица с сеткой, заголовок в две строки;
toc_pdf     — страница «Содержание» с отточиями, жирные нумерованные заголовки, поле и штамп ЕСКД, повёрнутый текст;
slides_pdf  — альбомные слайды: крупный заголовок вверху (на одном — со скрытой заглушкой макета), пункты, номер;
font_pdf    — без закладок и оглавления: заголовки крупнее основного текста;
scan_pdf    — страницы-картинки без текстового слоя.
"""
import io
from pathlib import Path

FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
]


def available():
    """Что мешает собрать тестовые PDF (пустая строка — всё есть)."""
    try:
        import reportlab  # noqa: F401
        import pdfplumber  # noqa: F401
    except ImportError as e:
        return f"нет пакета: {e.name}"
    if not _fonts():
        return "нет шрифта с кириллицей (DejaVu Sans или Arial)"
    return ""


def _fonts():
    for regular, bold in FONT_CANDIDATES:
        if Path(regular).exists():
            return regular, bold if Path(bold).exists() else regular
    return None


_REGISTERED = False


def _register():
    global _REGISTERED
    if _REGISTERED:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    regular, bold = _fonts()
    pdfmetrics.registerFont(TTFont("TF", regular))
    pdfmetrics.registerFont(TTFont("TFB", bold))
    _REGISTERED = True


def _canvas(size=None):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    _register()
    buf = io.BytesIO()
    return buf, canvas.Canvas(buf, pagesize=size or A4)


def _table(c, rows, x, y):
    from reportlab.platypus import Table, TableStyle
    t = Table(rows)
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "TF", 10), ("GRID", (0, 0), (-1, -1), 0.7, "black")]))
    _w, h = t.wrapOn(c, 400, 300)
    t.drawOn(c, x, y - h)
    return y - h - 20


HEADER = "Регламент эксплуатации АС «Учёт» — редакция 3"
RELIABILITY = [["Показатель", "Значение", "Ответственный"], ["RTO", "4 часа", "Служба эксплуатации"],
               ["Доступность", "99,5 %", "Владелец системы"]]


def outline_pdf():
    from reportlab.lib.pagesizes import A4
    W, H = A4
    buf, c = _canvas()
    pages = [
        [("h", 0, "1. Общие положения", None),
         ("p", ["Регламент определяет порядок эксплуатации автоматизированной системы «Учёт».",
                "Владелец системы — департамент информационных технологий."]),
         ("h", 1, "1.1 Назначение документа и область его применения для всех подсистем автоматизированной системы",
          ["1.1 Назначение документа и область его применения для всех", "подсистем автоматизированной системы"]),
         ("p", ["Документ обязателен для всех подразделений, эксплуатирующих систему."])],
        [("h", 0, "2. Требования к информационной безопасности", None),
         ("p", ["Передача персональных данных между подсистемами выполняется с шифро-",
                "ванием по ГОСТ Р 34.12-2015. Доступ администраторов — с двухфакторной",
                "аутентификацией."]),
         ("t", RELIABILITY)],
        [("h", 0, "3. Показатели надёжности", None),
         ("p", ["Время восстановления сервиса (RTO) — не более 4 часов.",
                "Допустимая потеря данных (RPO) — не более 1 часа."])],
    ]
    n = 0
    for pno, items in enumerate(pages, 1):
        c.setFont("TF", 8)
        c.drawString(50, H - 30, HEADER)
        c.drawString(W - 60, 25, str(pno))
        y = H - 80
        for it in items:
            if it[0] == "h":
                _kind, level, title, lines = it
                key = f"h{n}"
                n += 1
                c.bookmarkHorizontalAbsolute(key, y + 20)
                c.addOutlineEntry(title, key, level=level)
                c.setFont("TFB", 14)
                for line in lines or [title]:
                    c.drawString(60, y, line)
                    y -= 18
                y -= 8
            elif it[0] == "p":
                c.setFont("TF", 11)
                for line in it[1]:
                    c.drawString(60, y, line)
                    y -= 15
                y -= 10
            else:
                y = _table(c, it[1], 60, y)
        c.showPage()
    c.save()
    return buf.getvalue()


TOC_ITEMS = [("1. Введение", 2), ("2. Технические характеристики", 2), ("2.1 Габариты", 3), ("3. Монтаж", 4)]


def toc_pdf():
    from reportlab.lib.pagesizes import A4
    W, H = A4
    buf, c = _canvas()

    def frame(pno):
        c.setFont("TF", 7)
        c.drawString(12, 400, "Инв. № подл.")                 # поле ЕСКД слева
        c.drawString(70, 20, "Лист № докум. Подп. Дата")       # штамп внизу
        c.drawString(W - 40, 20, str(pno))
        c.saveState()
        c.translate(25, 300)
        c.rotate(90)
        c.drawString(0, 0, "Подп. и дата")                     # повёрнутый текст в поле
        c.restoreState()

    frame(1)
    c.setFont("TFB", 12)
    c.drawString(60, H - 80, "Содержание")
    c.setFont("TF", 12)
    y = H - 110
    for title, page in TOC_ITEMS:
        dots = " " + "." * max(5, 80 - len(title)) + " "
        c.drawString(60, y, f"{title}{dots}{page}")
        y -= 18
    c.showPage()
    body = {
        "1. Введение": ["Настоящее руководство описывает подготовку к эксплуатации комплекса InfoBox.",
                        "Монтаж выполняется с учётом требований безопасности."],
        "2. Технические характеристики": ["Комплекс поставляется в стоечном исполнении."],
        "2.1 Габариты": ["Высота корпуса — 1U, глубина — 450 мм, масса — 7 кг."],
        "3. Монтаж": ["Устройство крепится в стойку 19 дюймов четырьмя винтами."],
    }
    by_page = {}
    for title, page in TOC_ITEMS:
        by_page.setdefault(page, []).append(title)
    for pno in (2, 3, 4):
        frame(pno)
        y = H - 80
        for title in by_page.get(pno, []):
            c.setFont("TFB", 12)
            c.drawString(60, y, title)
            y -= 22
            c.setFont("TF", 12)
            for line in body[title]:
                c.drawString(60, y, line)
                y -= 16
            y -= 14
        c.showPage()
    c.save()
    return buf.getvalue()


SLIDES = [("Проблемы и актуальные угрозы", ["Сотни связей с внешними контрагентами", "Облачные решения"]),
          ("Аппаратное решение на DIN-рейку", ["Передача SPAN-трафика для IDS", "Не требует настройки"]),
          ("Сценарии применения", ["Энергетика", "Промышленное производство"])]


def slides_pdf():
    buf, c = _canvas((960, 540))
    for no, (title, bullets) in enumerate(SLIDES, 1):
        c.setFont("TFB", 28)
        if no == 2:                                   # скрытая заглушка макета под заголовком, как в PowerPoint
            c.setFillColorRGB(1, 1, 1)
            c.drawString(40, 480, "Образец заголовка")
            c.setFillColorRGB(0, 0, 0)
        c.drawString(40, 480, title)
        c.setFont("TF", 18)
        y = 400
        for b in bullets:
            c.drawString(60, y, "• " + b)
            y -= 32
        c.setFont("TF", 10)
        c.drawString(900, 20, str(no))
        c.showPage()
    c.save()
    return buf.getvalue()


def font_pdf():
    from reportlab.lib.pagesizes import A4
    W, H = A4
    buf, c = _canvas()
    blocks = [("TFB", 20, "Описание продукта InfoBox"), ("TF", 11, "Однонаправленная передача данных между сегментами."),
              ("TFB", 15, "Назначение"), ("TF", 11, "Защита технологического сегмента от воздействий извне."),
              ("TFB", 15, "Возможности"), ("TF", 11, "Передача файлов, журналов и потоков UDP в одну сторону.")]
    y = H - 80
    for font, size, text in blocks:
        c.setFont(font, size)
        c.drawString(60, y, text)
        y -= size + 14
    c.showPage()
    c.setFont("TF", 11)
    c.drawString(60, H - 80, "Поставка в стоечном исполнении; гарантия три года.")
    c.showPage()
    c.save()
    return buf.getvalue()


def scan_pdf():
    from PIL import Image, ImageDraw
    pages = []
    for i in range(2):
        img = Image.new("L", (827, 1169), 255)
        d = ImageDraw.Draw(img)
        for k in range(20):
            d.rectangle((80, 100 + k * 45, 700, 120 + k * 45), fill=0)    # «строки текста» картинкой
        pages.append(img)
    buf = io.BytesIO()
    pages[0].save(buf, "PDF", resolution=100, save_all=True, append_images=pages[1:])
    return buf.getvalue()
