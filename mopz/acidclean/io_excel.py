"""Загрузка исходных данных из Excel.

1. Шаблон AcidClean PRO (кнопка «Создать шаблон Excel») — листы «Скважина», «Муфты»,
   «История», «Инклинометрия».
2. Произвольные выгрузки истории (МЭР) и инклинометрии — заголовки распознаются по ключевым
   словам («Дата», «забойн», «нефт», «жидк», «обводн»; «Глубина», «Зенит», «Азимут»).
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from .models import ForecastPoint, HistoryRow, Port, Project, SurveyRow

# (раздел, атрибут, подпись, ед. изм.)
FIELDS = [
    ("well", "well", "№ скважины", ""),
    ("well", "pad", "Куст", ""),
    ("well", "field_name", "Месторождение", ""),
    ("well", "formation", "Пласт", ""),
    ("well", "customer", "Заказчик", ""),
    ("well", "report_date", "Дата отчёта", "ДД.ММ.ГГГГ"),
    ("well", "prepared_by", "Подготовил", ""),
    ("well", "checked_by", "Проверил", ""),
    ("construction", "casing_od", "Наружный диаметр ЭК", "мм"),
    ("construction", "casing_id", "Внутренний диаметр ЭК", "мм"),
    ("construction", "liner_od", "Наружный диаметр хвостовика", "мм"),
    ("construction", "liner_id", "Внутренний диаметр хвостовика", "мм"),
    ("construction", "tubing_od", "Наружный диаметр НКТ", "мм"),
    ("construction", "tubing_id", "Внутренний диаметр НКТ", "мм"),
    ("construction", "funnel_md", "Полированная воронка хвостовика (MD)", "м"),
    ("construction", "rotor_altitude", "Альтитуда ротора", "м"),
    ("construction", "reservoir_tvd", "TVD пласта от ротора (если нет инклинометрии)", "м"),
    ("reservoir", "p_res", "Пластовое давление текущее", "атм"),
    ("reservoir", "p_res_initial", "Пластовое давление начальное (для истории)", "атм"),
    ("reservoir", "t_res", "Пластовая температура", "°C"),
    ("reservoir", "perm", "Проницаемость пласта", "мД"),
    ("reservoir", "porosity", "Пористость пласта", "д.ед."),
    ("reservoir", "oil_visc", "Вязкость нефти пластовая", "сПз"),
    ("reservoir", "oil_density", "Плотность нефти", "г/см3"),
    ("reservoir", "water_density", "Плотность воды", "г/см3"),
    ("reservoir", "drainage_radius", "Радиус контура питания Rк", "м"),
    ("reservoir", "well_radius", "Радиус скважины rc", "м"),
    ("reservoir", "frac_pressure", "Давление ГРП (разрыва) на забое", "атм"),
    ("regime", "q_liq", "Дебит жидкости до ОПЗ", "м3/сут"),
    ("regime", "q_oil", "Дебит нефти до ОПЗ", "т/сут"),
    ("regime", "water_cut", "Обводнённость до ОПЗ", "%"),
    ("regime", "p_bhp", "Забойное давление", "атм"),
    ("regime", "skin_before", "Скин до ОПЗ (ГДИС, иначе 0,5)", ""),
    ("regime", "skin_source", "Источник скина", ""),
    ("design", "acid_name", "Кислотный состав", ""),
    ("design", "acid_density", "Плотность ГКС", "г/см3"),
    ("design", "acid_visc", "Вязкость ГКС", "сПз"),
    ("design", "flush_name", "Жидкость продавки", ""),
    ("design", "flush_density", "Плотность продавки", "г/см3"),
    ("design", "acid_mode", "Режим объёма ГКС (fixed / pore)", ""),
    ("design", "acid_volume", "Объём ГКС на порт", "м3"),
    ("design", "pore_fraction", "Доля порового объёма трещины (режим pore)", "д.ед."),
    ("design", "flush_volume", "Объём продавки на порт", "м3"),
    ("design", "rate", "Расход закачки", "м3/мин"),
    ("design", "pack_porosity", "Пористость пропантной пачки", "д.ед."),
    ("design", "skin_after_mode", "Скин после ОПЗ (fixed / calc)", ""),
    ("design", "skin_after", "Скин после ОПЗ (режим fixed)", ""),
    ("design", "injectivity", "Приемистость порта до ОПЗ", "м3/сут/атм"),
    ("design", "friction_factor", "Множитель потерь на трение", ""),
    ("design", "gap_minutes", "Пауза между портами на графике", "мин"),
    ("design", "forecast_mode", "Прогноз (exp — экспонента / table — по таблице)", ""),
    ("design", "forecast_decline", "Темп падения дебита (0 — по истории)", "%/мес"),
    ("design", "forecast_months", "Период прогноза", "мес"),
]

PORT_HEAD = ["№ муфты", "MD, м", "Xf, м", "H, м", "w, мм", "Проводимость, мД·м",
             "Проницаемость, мД", "Скин после ГРП", "Обрабатывать (да/нет)",
             "Объём ГКС, м3 (необяз.)", "Объём продавки, м3 (необяз.)"]
HIST_HEAD = ["Дата", "Рзаб, атм", "Qн, т/сут", "Qж, т/сут", "Обв., % вес.", "Рпл, атм (необяз.)"]
SURV_HEAD = ["MD, м", "Зенит, °", "Азимут, °"]
FC_HEAD = ["Месяц", "Qж, % от запускного", "Обв., % (необяз.)", "Рзаб, атм (необяз.)"]

BOLD = Font(bold=True)
FILL = PatternFill("solid", fgColor="F3E6E8")


def _hdr(ws, head):
    ws.append(head)
    for c in ws[1]:
        c.font = BOLD
        c.fill = FILL


def export_template(project: Project, path: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Скважина"
    _hdr(ws, ["Параметр", "Значение", "Ед. изм.", "Ключ"])
    for sec, attr, label, unit in FIELDS:
        ws.append([label, getattr(getattr(project, sec), attr), unit, f"{sec}.{attr}"])
    ws.column_dimensions["A"].width = 48
    ws.column_dimensions["B"].width = 26
    ws.column_dimensions["C"].width = 12
    ws.column_dimensions["D"].width = 26

    ws = wb.create_sheet("Муфты")
    _hdr(ws, PORT_HEAD)
    for p in project.ports:
        ws.append([p.number, p.md, p.xf, p.height, p.width_mm, p.conductivity, p.permeability,
                   p.skin_frac, "да" if p.treat else "нет", p.acid_volume, p.flush_volume])
    for i in range(len(PORT_HEAD)):
        ws.column_dimensions[chr(65 + i)].width = 16

    ws = wb.create_sheet("История")
    _hdr(ws, HIST_HEAD)
    for h in project.history:
        ws.append([h.date, h.p_bhp, h.q_oil, h.q_liq, h.water_cut, h.p_res])
    ws = wb.create_sheet("Инклинометрия")
    _hdr(ws, SURV_HEAD)
    for s in project.survey:
        ws.append([s.md, s.incl, s.azim])
    ws = wb.create_sheet("Прогноз")
    _hdr(ws, FC_HEAD)
    for r in project.forecast_table:
        ws.append([r.month, r.q_pct, r.water_cut, r.p_bhp])
    for col in "ABCD":
        ws.column_dimensions[col].width = 22
    wb.save(path)


def _f(v) -> Optional[float]:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", ".").replace(" ", ""))
    except ValueError:
        return None


def _date(v) -> str:
    if isinstance(v, datetime):
        return v.strftime("%d.%m.%Y")
    return str(v).strip() if v is not None else ""


def _sheet(wb, *names):
    for n in wb.sheetnames:
        if n.strip().lower() in [x.lower() for x in names]:
            return wb[n]
    return None


def import_template(path: str, project: Optional[Project] = None) -> Project:
    """Загрузка шаблона AcidClean PRO. Отсутствующие листы не меняют данные проекта."""
    wb = load_workbook(path, data_only=True)
    p = project or Project()
    ws = _sheet(wb, "Скважина")
    if ws is not None:
        by_key = {f"{s}.{a}": (s, a) for s, a, _, _ in FIELDS}
        by_label = {lbl.lower(): (s, a) for s, a, lbl, _ in FIELDS}
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or row[0] is None:
                continue
            key = row[3] if len(row) > 3 and row[3] in by_key else None
            sa = by_key.get(key) if key else by_label.get(str(row[0]).strip().lower())
            if not sa or row[1] is None:
                continue
            obj = getattr(p, sa[0])
            cur = getattr(obj, sa[1])
            val = row[1]
            if isinstance(cur, bool):
                val = str(val).strip().lower() in ("да", "1", "true", "yes")
            elif isinstance(cur, int) and not isinstance(cur, bool):
                val = int(_f(val) or 0)
            elif isinstance(cur, float):
                val = _f(val) or 0.0
            else:
                val = _date(val) if sa[1] == "report_date" else str(val)
            setattr(obj, sa[1], val)
    ws = _sheet(wb, "Муфты")
    if ws is not None:
        ports = []
        for r in ws.iter_rows(min_row=2, values_only=True):
            if not r or _f(r[0]) is None:
                continue
            r = list(r) + [None] * 11
            ports.append(Port(int(_f(r[0])), _f(r[1]) or 0, _f(r[2]) or 0, _f(r[3]) or 0, _f(r[4]) or 0,
                              _f(r[5]) or 0, _f(r[6]) or 0,
                              _f(r[7]) if _f(r[7]) is not None else -6.2,
                              str(r[8]).strip().lower() not in ("нет", "0", "false", "no"),
                              _f(r[9]), _f(r[10])))
        if ports:
            p.ports = ports
    ws = _sheet(wb, "История")
    if ws is not None:
        hist = read_history_ws(ws)
        if hist:
            p.history = hist
    ws = _sheet(wb, "Инклинометрия")
    if ws is not None:
        sv = read_survey_ws(ws)
        if sv:
            p.survey = sv
    ws = _sheet(wb, "Прогноз")
    if ws is not None:
        fc = []
        for r in ws.iter_rows(min_row=2, values_only=True):
            r = list(r or []) + [None] * 4
            if _f(r[0]) is None or _f(r[1]) is None:
                continue
            fc.append(ForecastPoint(int(_f(r[0])), _f(r[1]), _f(r[2]), _f(r[3])))
        if fc:
            p.forecast_table = fc
    return p


# ---------------------------------------------------------------------------
# Произвольные выгрузки
# ---------------------------------------------------------------------------
def _find_header(ws, must: List[str], scan=30):
    for i, row in enumerate(ws.iter_rows(min_row=1, max_row=scan, values_only=True), start=1):
        cells = [str(c).lower() if c is not None else "" for c in row]
        if all(any(m in c for c in cells) for m in must):
            return i, cells
    return None, None


def _col(cells, *keys, exclude=()):
    for j, c in enumerate(cells):
        if all(k in c for k in keys) and not any(e in c for e in exclude):
            return j
    return None


def read_history_ws(ws) -> List[HistoryRow]:
    hdr, cells = _find_header(ws, ["дата"])
    if hdr is None:
        return []
    cd = _col(cells, "дата")
    cp = _col(cells, "забой") if _col(cells, "забой") is not None else _col(cells, "рзаб")
    co = _col(cells, "нефт") if _col(cells, "нефт") is not None else _col(cells, "qн")
    cl = _col(cells, "жидк") if _col(cells, "жидк") is not None else _col(cells, "qж")
    cw = _col(cells, "обв") if _col(cells, "обв") is not None else _col(cells, "вод")
    cr = _col(cells, "рпл") if _col(cells, "рпл") is not None else _col(cells, "пласт")
    out = []
    for r in ws.iter_rows(min_row=hdr + 1, values_only=True):
        if r is None or cd is None or cd >= len(r) or r[cd] in (None, ""):
            continue
        g = lambda j: _f(r[j]) if j is not None and j < len(r) else None  # noqa: E731
        q_oil = g(co)
        if not q_oil and not g(cl):
            continue   # нет добычи (скважина в простое)
        out.append(HistoryRow(_date(r[cd]), g(cp), q_oil, g(cl), g(cw), g(cr)))
    return out


def read_survey_ws(ws) -> List[SurveyRow]:
    hdr, cells = _find_header(ws, ["зенит"])
    if hdr is None:
        hdr, cells = _find_header(ws, ["md"])
    if hdr is None:
        return []
    cm = _col(cells, "глубина") if _col(cells, "глубина") is not None else _col(cells, "md")
    ci = _col(cells, "зенит") if _col(cells, "зенит") is not None else _col(cells, "incl")
    ca = _col(cells, "азимут", exclude=("магн",))
    if ca is None:
        ca = _col(cells, "азимут")
    out = []
    for r in ws.iter_rows(min_row=hdr + 1, values_only=True):
        md, inc = (_f(r[cm]) if cm is not None else None), (_f(r[ci]) if ci is not None else None)
        if md is None or inc is None:
            continue
        az = _f(r[ca]) if ca is not None and ca < len(r) else 0.0
        out.append(SurveyRow(md, inc, az or 0.0))
    return out


def import_history(path: str) -> List[HistoryRow]:
    wb = load_workbook(path, data_only=True)
    for ws in wb.worksheets:
        h = read_history_ws(ws)
        if h:
            return h
    return []


def import_survey(path: str) -> List[SurveyRow]:
    wb = load_workbook(path, data_only=True)
    for ws in wb.worksheets:
        s = read_survey_ws(ws)
        if s:
            return s
    return []
