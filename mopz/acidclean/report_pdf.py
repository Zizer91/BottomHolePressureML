"""PDF-отчёт (reportlab)."""
from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

from . import charts
from . import report_text as rt
from .calc import CalcResult
from .models import Project
from .resources import asset

RED = colors.HexColor("#9B1B30")
LIGHT = colors.HexColor("#F3E6E8")
_FONTS = False


def _fonts():
    global _FONTS
    if not _FONTS:
        pdfmetrics.registerFont(TTFont("DejaVu", asset("DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", asset("DejaVuSans-Bold.ttf")))
        pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold",
                                      italic="DejaVu", boldItalic="DejaVu-Bold")
        _FONTS = True


def _styles():
    base = ParagraphStyle("base", fontName="DejaVu", fontSize=10, leading=14, alignment=TA_JUSTIFY)
    return {
        "body": ParagraphStyle("body", parent=base, firstLineIndent=10 * mm, spaceAfter=4),
        "plain": base,
        "cell": ParagraphStyle("cell", parent=base, fontSize=8, leading=10, alignment=0),
        "cellc": ParagraphStyle("cellc", parent=base, fontSize=8, leading=10, alignment=TA_CENTER),
        "h1": ParagraphStyle("h1", parent=base, fontName="DejaVu-Bold", fontSize=14, leading=18,
                             spaceBefore=6, spaceAfter=8, textColor=RED),
        "h2": ParagraphStyle("h2", parent=base, fontName="DejaVu-Bold", fontSize=11, leading=15,
                             spaceBefore=6, spaceAfter=4),
        "caption": ParagraphStyle("caption", parent=base, fontSize=9, alignment=TA_CENTER,
                                  spaceBefore=2, spaceAfter=8),
        "tcap": ParagraphStyle("tcap", parent=base, fontSize=9, spaceBefore=6, spaceAfter=3),
        "title": ParagraphStyle("title", parent=base, fontName="DejaVu-Bold", fontSize=22, leading=28,
                                alignment=TA_CENTER, textColor=RED),
        "center": ParagraphStyle("center", parent=base, alignment=TA_CENTER, fontSize=11, leading=16),
        "bullet": ParagraphStyle("bullet", parent=base, leftIndent=6 * mm, bulletIndent=1 * mm,
                                 spaceAfter=3),
    }


def _table(head, rows, st, widths=None, first_col_left=True):
    data = [[Paragraph(f"<b>{h}</b>", st["cellc"]) for h in head]]
    for r in rows:
        data.append([Paragraph(str(c), st["cell"] if (i == 0 and first_col_left) else st["cellc"])
                     for i, c in enumerate(r)])
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="CENTER")
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def _fig_image(fig, width):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160)
    buf.seek(0)
    w, h = fig.get_size_inches()
    return Image(buf, width=width, height=width * h / w)


def build_pdf(project: Project, res: CalcResult, path: str) -> None:
    _fonts()
    st = _styles()
    page_w, page_h = A4
    margin = 18 * mm
    frame_w = page_w - 2 * margin

    def on_page(canvas, doc):
        canvas.saveState()
        try:
            canvas.drawImage(asset("logo.png"), margin, page_h - 16 * mm, width=27 * mm,
                             height=12 * mm, preserveAspectRatio=True, mask="auto")
        except Exception:
            pass
        canvas.setFont("DejaVu-Bold", 9)
        canvas.setFillColor(RED)
        canvas.drawRightString(page_w - margin, page_h - 11 * mm, rt.APP_NAME)
        canvas.setFont("DejaVu", 8)
        canvas.setFillColor(colors.black)
        w = project.well
        canvas.drawRightString(page_w - margin, page_h - 15 * mm,
                               f"Скв. {w.well} куст {w.pad}, {w.field_name}")
        canvas.setStrokeColor(RED)
        canvas.setLineWidth(1.5)
        canvas.line(margin, page_h - 18 * mm, page_w - margin, page_h - 18 * mm)
        canvas.setStrokeColor(colors.grey)
        canvas.setLineWidth(0.5)
        canvas.line(margin, 14 * mm, page_w - margin, 14 * mm)
        canvas.setFont("DejaVu", 8)
        canvas.drawRightString(page_w - margin, 10 * mm, str(doc.page))
        canvas.drawString(margin, 10 * mm, f"{rt.APP_NAME} · Дизайн ОПЗ · {w.report_date}")
        canvas.restoreState()

    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=margin, rightMargin=margin,
                            topMargin=24 * mm, bottomMargin=20 * mm,
                            title=f"{rt.APP_NAME} — дизайн ОПЗ скв. {project.well.well}",
                            author=project.well.prepared_by or rt.APP_NAME)
    s = []
    P = lambda t, k="body": Paragraph(t, st[k])  # noqa: E731
    fig_n = [0]
    tab_n = [0]

    def tcap(text):
        tab_n[0] += 1
        return P(f"Таблица {tab_n[0]} – {text}", "tcap")

    def figure(fig, text):
        fig_n[0] += 1
        return KeepTogether([_fig_image(fig, frame_w), P(f"Рисунок {fig_n[0]} – {text}", "caption")])

    # ---- титульный лист
    s += [Spacer(1, 25 * mm)]
    try:
        s.append(Image(asset("logo.png"), width=70 * mm, height=70 * mm * 548 / 1228))
    except Exception:
        pass
    s += [Spacer(1, 12 * mm), P(f"{rt.APP_NAME} Отчёт", "title"), Spacer(1, 4 * mm),
          P("<b>Дизайн моделирования процесса ОПЗ (МОПЗ)</b>", "center")]
    s += [P(t, "center") for t in rt.title_lines(project)]
    s += [Spacer(1, 10 * mm), P("Резюме", "h2")]
    pr = res.prod
    s.append(P(f"Закачка {rt.f(res.total_acid, 1)} м3 {project.design.acid_name} в "
               f"{len([x for x in res.ports if x.port.treat])} муфт(ы) ГРП. Ожидаемый дебит нефти "
               f"{rt.f(pr.q_oil_before)} → {rt.f(pr.q_oil_after)} т/сут, жидкости "
               f"{rt.f(pr.q_liq_before, 1)} → {rt.f(pr.q_liq_after, 1)} м3/сут, скин "
               f"{pr.skin_before:+.1f} → {pr.skin_after:+.1f}. Дополнительная добыча нефти за год — "
               f"{rt.f(res.forecast.extra_oil_total, 0)} т.", "plain"))
    s += [Spacer(1, 8 * mm), P("Содержание", "h2")]
    for item in ("Обозначения и сокращения", "Введение", "1. Исходные данные", "2. Дизайн ОПЗ",
                 "3. Ожидаемые параметры работы скважины", "Заключение"):
        s.append(P(item, "plain"))
    s += [Spacer(1, 15 * mm), P(f"Подготовлено: {project.well.prepared_by}", "plain"),
          P(f"Проверено: {project.well.checked_by}", "plain"), PageBreak()]

    # ---- обозначения и введение
    s.append(P("Обозначения и сокращения", "h1"))
    s += [P(a, "plain") for a in rt.abbreviations()]
    s += [Spacer(1, 6 * mm), P("Введение", "h1")]
    s += [P(t) for t in rt.introduction(project, res)]
    if project.notes:
        s.append(P(project.notes))

    # ---- 1. исходные данные
    s += [PageBreak(), P("1. Исходные данные", "h1")]
    s.append(tcap("Исходные данные по конструкции и оборудованию"))
    s.append(_table(["Параметр", "Значение", "Ед. изм."],
                    [list(r) for r in rt.table_construction(project, res)], st,
                    [frame_w * 0.55, frame_w * 0.3, frame_w * 0.15]))
    s.append(tcap("Используемые реагенты"))
    d = project.design
    s.append(_table(["№", "Название", "Плотность, г/см3"],
                    [["1", d.acid_name, rt.f(d.acid_density)], ["2", d.flush_name, rt.f(d.flush_density)]],
                    st, [frame_w * 0.1, frame_w * 0.6, frame_w * 0.3]))
    s.append(tcap("Пластовые данные и режим работы до ОПЗ"))
    s.append(_table(["Параметр", "Значение", "Ед. изм."],
                    [list(r) for r in rt.table_reservoir(project, res)], st,
                    [frame_w * 0.55, frame_w * 0.2, frame_w * 0.25]))
    head, rows = rt.table_fractures(project, res)
    n = len(head) - 2
    s.append(tcap("Параметры закреплённых трещин ГРП и объёмы ГКС по портам"))
    s.append(_table(head, rows, st, [frame_w * 0.34, frame_w * 0.08] + [frame_w * 0.58 / max(n, 1)] * n))
    s.append(Spacer(1, 4 * mm))
    s.append(figure(charts.history_chart(res),
                    "Диаграмма работы скважины с указанием потери продуктивности (входной контроль)"))

    # ---- 2. дизайн
    s += [PageBreak(), P("2. Дизайн ОПЗ", "h1")]
    s.append(P("Для калибровки и корректного расчёта устьевого давления при проведении ОПЗ "
               "рекомендуется проведение теста на приемистость, анализ результатов и выполнение "
               "редизайна."))
    s.append(tcap("План закачки. Дизайн ОПЗ"))
    head, rows = rt.table_plan(project, res)
    s.append(_table(head, rows, st, [w * frame_w for w in (0.05, 0.13, 0.11, 0.27, 0.1, 0.1, 0.1, 0.14)],
                    first_col_left=False))
    s.append(Spacer(1, 4 * mm))
    s.append(figure(charts.fracture_detail(res),
                    "Прохождение кислотной композиции по закреплённой трещине ГРП (разлиновка расстояния)"))
    s.append(figure(charts.fracture_plan(res), "Схема трещин ГРП и зоны промывки ГКС"))
    fp = project.reservoir.frac_pressure
    s.append(figure(charts.pumping_chart(res, fp, 1), "Режим закачки. Дизайн ОПЗ. Стадия 1"))
    s.append(figure(charts.pumping_chart(res, fp), "Режимы технологических закачек на все стадии"))
    s.append(tcap("Расчётные давления закачки по стадиям"))
    head, rows = rt.table_pumping(res)
    s.append(_table(head, rows, st, None, first_col_left=False))
    s.append(Spacer(1, 4 * mm))
    s.append(figure(charts.skin_chart(res), "Изменение скин-фактора по зонам обработки"))
    s.append(tcap("Результаты обработки. Дизайн ОПЗ"))
    head, rows = rt.table_results(res)
    s.append(_table(head, rows, st, [frame_w * 0.46, frame_w * 0.18, frame_w * 0.18, frame_w * 0.18]))

    # ---- 3. прогноз
    s += [PageBreak(), P("3. Ожидаемые параметры работы скважины", "h1")]
    s.append(P(rt.forecast_method(res)))
    s.append(figure(charts.forecast_chart(res),
                    "Диаграмма работы скважины с планируемыми параметрами (Qж, Qн, % обв., Рзаб) на 1 год"))
    s.append(tcap("Планируемые параметры работы скважины по месяцам"))
    head, rows = rt.table_forecast(res)
    s.append(_table(head, rows, st, None, first_col_left=False))

    # ---- заключение
    s += [Spacer(1, 6 * mm), P("Заключение", "h1")]
    s += [Paragraph(t, st["bullet"], bulletText="•") for t in rt.conclusions(project, res)]

    doc.build(s, onFirstPage=on_page, onLaterPages=on_page)
