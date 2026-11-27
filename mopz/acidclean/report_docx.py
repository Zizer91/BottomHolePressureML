"""DOCX-отчёт (python-docx) — редактируемая версия отчёта, структура как у PDF."""
from __future__ import annotations

import io

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from . import charts
from . import report_text as rt
from .calc import CalcResult
from .models import Project
from .resources import asset

RED = RGBColor(0x9B, 0x1B, 0x30)
HEAD_FILL = "F3E6E8"
FONT = "Times New Roman"


# ---------------------------------------------------------------------------
# вспомогательные функции
# ---------------------------------------------------------------------------
def _shade(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def _repeat_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    tr_pr.append(el)


def _field(paragraph, instr, placeholder=""):
    """Вставить поле Word (PAGE, TOC …)."""
    run = paragraph.add_run()
    b = OxmlElement("w:fldChar")
    b.set(qn("w:fldCharType"), "begin")
    run._r.append(b)
    run = paragraph.add_run()
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = instr
    run._r.append(it)
    run = paragraph.add_run()
    s = OxmlElement("w:fldChar")
    s.set(qn("w:fldCharType"), "separate")
    run._r.append(s)
    paragraph.add_run(placeholder)
    run = paragraph.add_run()
    e = OxmlElement("w:fldChar")
    e.set(qn("w:fldCharType"), "end")
    run._r.append(e)


def _no_borders(table):
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "nil")
        borders.append(el)
    tbl_pr.append(borders)


def _set_font(style, size, bold=None, color=None):
    style.font.name = FONT
    style.font.size = Pt(size)
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), FONT)
    if bold is not None:
        style.font.bold = bold
    if color is not None:
        style.font.color.rgb = color


def _fig_png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=170)
    buf.seek(0)
    return buf


class _Doc:
    def __init__(self, project: Project):
        self.doc = Document()
        self.project = project
        self.fig_n = 0
        self.tab_n = 0
        st = self.doc.styles
        _set_font(st["Normal"], 12)
        st["Normal"].paragraph_format.space_after = Pt(4)
        for name, size in (("Heading 1", 15), ("Heading 2", 13), ("Title", 24)):
            _set_font(st[name], size, bold=True, color=RED)
        st["Heading 1"].paragraph_format.space_before = Pt(12)
        st["Heading 1"].paragraph_format.space_after = Pt(8)
        sec = self.doc.sections[0]
        sec.orientation = WD_ORIENT.PORTRAIT
        sec.page_width, sec.page_height = Cm(21), Cm(29.7)
        sec.left_margin = Cm(2.5)
        sec.right_margin = Cm(1.5)
        sec.top_margin = sec.bottom_margin = Cm(2)
        self.width = sec.page_width - sec.left_margin - sec.right_margin
        self._header_footer(sec)

    def _header_footer(self, sec):
        w = self.project.well
        hdr = sec.header
        t = hdr.add_table(rows=1, cols=2, width=self.width)
        _no_borders(t)
        c0, c1 = t.rows[0].cells
        try:
            c0.paragraphs[0].add_run().add_picture(asset("logo.png"), width=Cm(2.6))
        except Exception:
            pass
        p = c1.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r = p.add_run(rt.APP_NAME + "\n")
        r.bold = True
        r.font.size = Pt(9)
        r.font.color.rgb = RED
        r = p.add_run(f"Скв. {w.well} куст {w.pad}, {w.field_name}")
        r.font.size = Pt(8)
        if hdr.paragraphs and not hdr.paragraphs[0].text:
            hdr.paragraphs[0]._p.getparent().remove(hdr.paragraphs[0]._p)
        fp = sec.footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r = fp.add_run(f"{rt.APP_NAME} · Дизайн ОПЗ · {w.report_date}    стр. ")
        r.font.size = Pt(8)
        _field(fp, "PAGE", "1")

    # -------------------------------------------------------------- блоки
    def p(self, text, bold=False, align=None, size=None, indent=True, italic=False):
        para = self.doc.add_paragraph()
        if indent:
            para.paragraph_format.first_line_indent = Cm(1.25)
        para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY if align is None else align
        run = para.add_run(text)
        run.bold = bold
        run.italic = italic
        if size:
            run.font.size = Pt(size)
        return para

    def h1(self, text):
        return self.doc.add_heading(text, level=1)

    def page_break(self):
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    def caption_table(self, text):
        self.tab_n += 1
        para = self.p(f"Таблица {self.tab_n} – {text}", indent=False, align=WD_ALIGN_PARAGRAPH.LEFT, size=11)
        para.paragraph_format.keep_with_next = True
        para.paragraph_format.space_before = Pt(6)

    def table(self, head, rows, widths=None, first_left=True):
        t = self.doc.add_table(rows=1, cols=len(head))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for j, h in enumerate(head):
            cell = t.rows[0].cells[j]
            cell.text = ""
            run = cell.paragraphs[0].add_run(str(h))
            run.bold = True
            run.font.size = Pt(9)
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            _shade(cell, HEAD_FILL)
        _repeat_header(t.rows[0])
        for r in rows:
            cells = t.add_row().cells
            for j, v in enumerate(r):
                cells[j].text = ""
                para = cells[j].paragraphs[0]
                run = para.add_run(str(v))
                run.font.size = Pt(9)
                para.alignment = (WD_ALIGN_PARAGRAPH.LEFT if (j == 0 and first_left)
                                  else WD_ALIGN_PARAGRAPH.CENTER)
                para.paragraph_format.space_after = Pt(0)
        if not widths:
            widths = [1.6] + [1.0] * (len(head) - 1) if first_left else [1.0] * len(head)
        total = sum(widths)
        t.autofit = False
        grid = t._tbl.tblGrid
        for j, wd in enumerate(widths):
            w = int(self.width * wd / total)
            t.columns[j].width = w
            grid.gridCol_lst[j].w = w
            for row in t.rows:
                row.cells[j].width = w
        self.doc.add_paragraph().paragraph_format.space_after = Pt(2)
        return t

    def figure(self, fig, caption):
        self.fig_n += 1
        para = self.doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.keep_with_next = True
        w, h = fig.get_size_inches()
        width = self.width
        max_h = Cm(20)
        if width * h / w > max_h:
            width = int(max_h * w / h)
        para.add_run().add_picture(_fig_png(fig), width=width)
        cap = self.p(f"Рисунок {self.fig_n} – {caption}", indent=False,
                     align=WD_ALIGN_PARAGRAPH.CENTER, size=11)
        cap.paragraph_format.space_after = Pt(10)

    def bullets(self, items):
        for t in items:
            para = self.doc.add_paragraph(style="List Bullet")
            para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            para.add_run(t)


def build_docx(project: Project, res: CalcResult, path: str) -> None:
    d = _Doc(project)
    doc = d.doc
    pr = res.prod
    tr_count = len([x for x in res.ports if x.port.treat])

    # ---- титульный лист
    for _ in range(3):
        doc.add_paragraph()
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    try:
        para.add_run().add_picture(asset("logo.png"), width=Cm(7))
    except Exception:
        pass
    t = doc.add_paragraph(style="Title")
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    t.add_run(f"{rt.APP_NAME} Отчёт")
    d.p("Дизайн моделирования процесса ОПЗ (МОПЗ)", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False)
    for line in rt.title_lines(project):
        d.p(line, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False)
    doc.add_paragraph()
    d.p("Резюме", bold=True, indent=False)
    d.p(f"Закачка {rt.f(res.total_acid, 1)} м3 {project.design.acid_name} в {tr_count} муфт(ы) ГРП. "
        f"Ожидаемый дебит нефти {rt.f(pr.q_oil_before)} → {rt.f(pr.q_oil_after)} т/сут, жидкости "
        f"{rt.f(pr.q_liq_before, 1)} → {rt.f(pr.q_liq_after, 1)} м3/сут, скин {pr.skin_before:+.1f} → "
        f"{pr.skin_after:+.1f}. Дополнительная добыча нефти за год — {rt.f(res.forecast.extra_oil_total, 0)} т.")
    doc.add_paragraph()
    d.p("Содержание", bold=True, indent=False)
    toc = doc.add_paragraph()
    _field(toc, 'TOC \\o "1-1" \\h \\z \\u',
           "Чтобы обновить содержание: правый клик → «Обновить поле» (или F9).")
    doc.add_paragraph()
    d.p(f"Подготовлено: {project.well.prepared_by}", indent=False)
    d.p(f"Проверено: {project.well.checked_by}", indent=False)
    d.page_break()

    # ---- обозначения, введение
    d.h1("Обозначения и сокращения")
    for a in rt.abbreviations():
        d.p(a, indent=False)
    d.h1("Введение")
    for txt in rt.introduction(project, res):
        d.p(txt)
    if project.notes:
        d.p(project.notes)

    # ---- 1. исходные данные
    d.page_break()
    d.h1("1. Исходные данные")
    d.caption_table("Исходные данные по конструкции и оборудованию")
    d.table(["Параметр", "Значение", "Ед. изм."], [list(r) for r in rt.table_construction(project, res)],
            [55, 30, 15])
    dz = project.design
    d.caption_table("Используемые реагенты")
    d.table(["№", "Название", "Плотность, г/см3"],
            [["1", dz.acid_name, rt.f(dz.acid_density)], ["2", dz.flush_name, rt.f(dz.flush_density)]],
            [10, 60, 30], first_left=False)
    d.caption_table("Пластовые данные и режим работы до ОПЗ")
    d.table(["Параметр", "Значение", "Ед. изм."], [list(r) for r in rt.table_reservoir(project, res)],
            [55, 20, 25])
    head, rows = rt.table_fractures(project, res)
    n = len(head) - 2
    d.caption_table("Параметры закреплённых трещин ГРП и объёмы ГКС по портам")
    d.table(head, rows, [34, 8] + [58 / max(n, 1)] * n)
    if project.survey:
        ports = project.ports
        d.figure(charts.survey_chart(project.survey, ports, project.construction.funnel_md),
                 "Геометрия ствола скважины по данным инклинометрии")
    d.figure(charts.history_chart(res),
             "Диаграмма работы скважины с указанием потери продуктивности (входной контроль)")

    # ---- 2. дизайн
    d.page_break()
    d.h1("2. Дизайн ОПЗ")
    d.p("Для калибровки и корректного расчёта устьевого давления при проведении ОПЗ рекомендуется "
        "проведение теста на приемистость, анализ результатов и выполнение редизайна.")
    d.caption_table("План закачки. Дизайн ОПЗ")
    head, rows = rt.table_plan(project, res)
    d.table(head, rows, [5, 13, 11, 27, 10, 10, 10, 14], first_left=False)
    d.figure(charts.fracture_detail(res),
             "Прохождение кислотной композиции по закреплённой трещине ГРП (разлиновка расстояния)")
    d.figure(charts.fracture_plan(res), "Схема трещин ГРП и зоны промывки ГКС")
    fp = project.reservoir.frac_pressure
    d.figure(charts.pumping_chart(res, fp, 1), "Режим закачки. Дизайн ОПЗ. Стадия 1")
    d.figure(charts.pumping_chart(res, fp), "Режимы технологических закачек на все стадии")
    d.caption_table("Расчётные давления закачки по стадиям")
    head, rows = rt.table_pumping(res)
    d.table(head, rows, first_left=False)
    d.figure(charts.skin_chart(res), "Изменение скин-фактора по зонам обработки")
    d.caption_table("Результаты обработки. Дизайн ОПЗ")
    head, rows = rt.table_results(res)
    d.table(head, rows, [46, 18, 18, 18])

    # ---- 3. прогноз
    d.page_break()
    d.h1("3. Ожидаемые параметры работы скважины")
    d.p(rt.forecast_method(res))
    d.figure(charts.forecast_chart(res),
             "Диаграмма работы скважины с планируемыми параметрами (Qж, Qн, % обв., Рзаб) на 1 год")
    d.caption_table("Планируемые параметры работы скважины по месяцам")
    head, rows = rt.table_forecast(res)
    d.table(head, rows, first_left=False)

    # ---- заключение
    d.h1("Заключение")
    d.bullets(rt.conclusions(project, res))

    doc.core_properties.title = f"{rt.APP_NAME} — дизайн ОПЗ скв. {project.well.well}"
    doc.core_properties.author = project.well.prepared_by or rt.APP_NAME
    doc.save(path)
