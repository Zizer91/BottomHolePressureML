"""XLSX-отчёт (openpyxl)."""
from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from . import charts
from . import report_text as rt
from .calc import CalcResult
from .models import Project
from .resources import asset

RED = "9B1B30"
HEAD_FILL = PatternFill("solid", fgColor="F3E6E8")
THIN = Side(style="thin", color="999999")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _num(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return v


def _write_table(ws, row, head, rows, title=None):
    if title:
        ws.cell(row=row, column=1, value=title).font = Font(bold=True, color=RED)
        row += 1
    for j, h in enumerate(head, start=1):
        c = ws.cell(row=row, column=j, value=h)
        c.font = Font(bold=True)
        c.fill = HEAD_FILL
        c.border = BORDER
        c.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
    for r in rows:
        row += 1
        for j, v in enumerate(r, start=1):
            c = ws.cell(row=row, column=j, value=_num(v) if j > 1 else v)
            c.border = BORDER
            c.alignment = Alignment(wrap_text=True, vertical="center")
    return row + 2


def _widths(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _img(fig, width_px=900):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110)
    buf.seek(0)
    im = XLImage(buf)
    k = width_px / im.width
    im.width, im.height = width_px, im.height * k
    return im


def build_xlsx(project: Project, res: CalcResult, path: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Сводка"
    try:
        logo = XLImage(asset("logo.png"))
        logo.width, logo.height = 160, 160 * 548 / 1228
        ws.add_image(logo, "A1")
    except Exception:
        pass
    ws["C2"] = f"{rt.APP_NAME} — дизайн ОПЗ"
    ws["C2"].font = Font(bold=True, size=16, color=RED)
    for i, t in enumerate(rt.title_lines(project)):
        ws.cell(row=3 + i, column=3, value=t)
    row = 7
    head, rows = rt.table_results(res)
    row = _write_table(ws, row, head, rows, "Результаты обработки")
    ws.cell(row=row, column=1, value="Заключение").font = Font(bold=True, color=RED)
    for t in rt.conclusions(project, res):
        row += 1
        ws.cell(row=row, column=1, value="• " + t).alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
        ws.row_dimensions[row].height = 15 * (1 + len(t) // 95)
    _widths(ws, [46, 18, 18, 18])

    ws = wb.create_sheet("Исходные данные")
    row = _write_table(ws, 1, ["Параметр", "Значение", "Ед. изм."],
                       [list(r) for r in rt.table_construction(project, res)], "Конструкция и оборудование")
    d = project.design
    row = _write_table(ws, row, ["Реагент", "Плотность, г/см3", ""],
                       [[d.acid_name, d.acid_density, ""], [d.flush_name, d.flush_density, ""]], "Реагенты")
    _write_table(ws, row, ["Параметр", "Значение", "Ед. изм."],
                 [list(r) for r in rt.table_reservoir(project, res)], "Пласт и режим до ОПЗ")
    _widths(ws, [55, 22, 30])

    ws = wb.create_sheet("Трещины ГРП")
    head, rows = rt.table_fractures(project, res)
    _write_table(ws, 1, head, rows, "Параметры трещин и объёмы ГКС по портам")
    _widths(ws, [38, 8] + [12] * (len(head) - 2))

    ws = wb.create_sheet("План закачки")
    head, rows = rt.table_plan(project, res)
    row = _write_table(ws, 1, head, rows, "План закачки (дизайн ОПЗ)")
    head, rows = rt.table_pumping(res)
    _write_table(ws, row, head, rows, "Расчётные давления по стадиям")
    _widths(ws, [6, 16, 14, 34, 12, 12, 12, 14])

    ws = wb.create_sheet("Режим закачки")
    head = ["Время, мин", "Стадия", "Расход, м3/мин", "Рзаб, атм", "Руст, атм", "Скин", "В пласт",
            "ГКС в пласте, м3"]
    rows = [[round(p.t, 2), p.stage, p.rate, round(p.p_bh, 1), round(p.p_wh, 1), round(p.skin, 3),
             p.fluid, round(p.acid_in, 2)] for p in res.pumping.points]
    _write_table(ws, 1, head, rows)
    _widths(ws, [12, 8, 14, 12, 12, 10, 12, 16])

    ws = wb.create_sheet("Прогноз")
    head, rows = rt.table_forecast(res)
    _write_table(ws, 1, head, rows, "Планируемые параметры на 1 год")
    _widths(ws, [10, 14, 14, 10, 12, 18, 16])

    if res.history:
        ws = wb.create_sheet("Входной контроль")
        head = ["Дата", "Рзаб, атм", "Рпл, атм", "Qн, т/сут", "Qж, т/сут", "Qж, м3/сут", "Обв., %",
                "Кпрод, м3/сут/атм"]
        rows = [[h.date.strftime("%d.%m.%Y"), h.p_bhp, h.p_res and round(h.p_res, 1), h.q_oil, h.q_liq,
                 h.q_liq_m3 and round(h.q_liq_m3, 2), h.water_cut, h.kprod and round(h.kprod, 4)]
                for h in res.history]
        _write_table(ws, 1, head, rows, "История эксплуатации")
        _widths(ws, [12, 10, 10, 10, 10, 12, 10, 16])

    ws = wb.create_sheet("Графики")
    row = 1
    for key, title, fig in charts.all_charts(res, project.reservoir.frac_pressure):
        ws.cell(row=row, column=1, value=title).font = Font(bold=True, color=RED)
        im = _img(fig)
        ws.add_image(im, f"A{row + 1}")
        row += int(im.height / 20) + 3
    wb.save(path)
