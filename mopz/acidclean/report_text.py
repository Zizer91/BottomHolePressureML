"""Общие таблицы и тексты отчёта (используются и в PDF, и в XLSX)."""
from __future__ import annotations

from typing import List, Tuple

from .calc import CalcResult, treated
from .models import Project

APP_NAME = "AcidClean PRO"


def f(v, nd=2):
    if v is None:
        return "—"
    if isinstance(v, (int, float)):
        return f"{v:.{nd}f}"
    return str(v)


def title_lines(p: Project) -> List[str]:
    w = p.well
    return [f"Скважина: {w.well}-{w.pad}, {w.field_name} месторождение, {w.formation}",
            f"Дата: {w.report_date}"]


def abbreviations() -> List[str]:
    return ["ГКС – глинокислотный состав", "ГРП – гидравлический разрыв пласта",
            "МГРП – многостадийный гидравлический разрыв пласта",
            "ОПЗ – обработка призабойной зоны", "НКТ – насосно-компрессорная труба",
            "Кпрод – коэффициент продуктивности", "Xf, H, w – закреплённые полудлина, высота и ширина трещины"]


def introduction(p: Project, r: CalcResult) -> List[str]:
    d = p.design
    return [
        f"Расчёт дизайна ОПЗ выполнен в программе «{APP_NAME}» по данным конструкции скважины, "
        "оборудования, отчётов ГРП по стадиям, истории эксплуатации и результатов геофизических "
        "исследований.",
        "Объёмы кислотной композиции рассчитаны с учётом фактической закреплённой трещины ГРП "
        "каждой стадии (полудлина, высота, ширина, пористость пропантной пачки).",
        "Ожидаемые запускные параметры рассчитаны по формуле Дюпюи, нормированной на фактический "
        f"режим работы скважины. Скин-фактор до ОПЗ: {r.prod.skin_before:+.1f} "
        f"({p.regime.skin_source}).",
        f"Принято, что обводнённость не изменится, забойное давление останется {f(p.regime.p_bhp, 0)} атм. "
        f"Скважина заполнена до устья технической жидкостью плотностью {f(d.flush_density)} г/см3.",
    ]


def table_construction(p: Project, r: CalcResult) -> List[Tuple[str, str, str]]:
    c = p.construction
    tr = treated(r.ports)
    return [
        ("Внешний диаметр обсадной колонны", f(c.casing_od, 1), "мм"),
        ("Внутренний диаметр обсадной колонны", f(c.casing_id, 1), "мм"),
        ("Внешний диаметр хвостовика", f(c.liner_od, 1), "мм"),
        ("Внутренний диаметр хвостовика", f(c.liner_id, 1), "мм"),
        ("Внешний диаметр НКТ", f(c.tubing_od, 1), "мм"),
        ("Внутренний диаметр НКТ", f(c.tubing_id, 1), "мм"),
        ("Полированная воронка хвостовика", f(c.funnel_md) if c.funnel_md else "—", "м"),
        ("Общая длина интервалов ОПЗ (по закреплённой высоте трещин)", f(r.total_height, 1), "м"),
        ("Обрабатываемые интервалы (муфты МГРП)", "; ".join(f(x.port.md) for x in tr), "м"),
    ]


def table_reservoir(p: Project, r: CalcResult) -> List[Tuple[str, str, str]]:
    res, reg = p.reservoir, p.regime
    return [
        ("Пластовое давление", f(res.p_res, 0), "атм"),
        ("Пластовая температура", f(res.t_res, 0), "°C"),
        ("Проницаемость пласта", f(res.perm, 2), "мД"),
        ("Вязкость нефти в пластовых условиях", f(res.oil_visc, 2), "сПз"),
        ("Давление ГРП (разрыва) на забое", f(res.frac_pressure, 0) if res.frac_pressure else "—", "атм"),
        ("Радиус контура питания Rк / радиус скважины rc", f"{f(res.drainage_radius, 0)} / {f(res.well_radius, 3)}", "м"),
        ("Дебит жидкости до ОПЗ", f(reg.q_liq, 1), "м3/сут"),
        ("Дебит нефти до ОПЗ", f(reg.q_oil, 2), "т/сут"),
        ("Обводнённость", f(reg.water_cut, 1), "%"),
        ("Забойное давление", f(reg.p_bhp, 0), "атм"),
        ("Скин-фактор до ОПЗ", f(reg.skin_before, 1), reg.skin_source),
    ]


def table_fractures(p: Project, r: CalcResult):
    tr = treated(r.ports)
    phi = p.design.pack_porosity
    head = ["Параметр", "Ед."] + [f"МГРП{x.port.number}" for x in tr]
    rows = [
        ("Глубина муфты (MD)", "м", [f(x.port.md) for x in tr]),
        ("Глубина муфты (TVD)", "м", [f(x.tvd, 1) for x in tr]),
        ("Закреплённая полудлина трещины Xf", "м", [f(x.port.xf, 1) for x in tr]),
        ("Закреплённая высота трещины H", "м", [f(x.port.height, 1) for x in tr]),
        ("Закреплённая ширина трещины w", "мм", [f(x.port.width_mm, 1) for x in tr]),
        ("Проводимость трещины", "мД·м", [f(x.port.conductivity, 0) for x in tr]),
        ("Проницаемость трещины", "мД", [f(x.port.permeability, 0) for x in tr]),
        ("Объём трещины", "м3", [f(x.frac_volume) for x in tr]),
        (f"Поровый объём при φ={phi:g}", "м3", [f(x.pore_volume) for x in tr]),
        ("Объём ГКС", "м3", [f(x.acid_volume, 1) for x in tr]),
        ("Глубина проникновения ГКС", "м", [f(x.penetration, 1) for x in tr]),
        ("Доля промытой полудлины", "%", [f(x.fraction * 100, 0) for x in tr]),
        ("Скин-фактор после ОПЗ", "—", [f(x.skin_after, 1) for x in tr]),
    ]
    return head, [[a, b] + c for a, b, c in rows]


def table_plan(p: Project, r: CalcResult):
    head = ["№", "Стадия", "Тип стадии", "Тип жидкости", "Q, м3/мин", "Объём, м3", "Время, мин",
            "Нсп. НКТ, м"]
    rows = []
    for x in r.plan:
        rows.append([str(x.n), f"{x.stage} (МГРП{x.port_number})", x.kind, x.fluid, f(x.rate),
                     f(x.volume, 1), f(x.minutes, 0), f(x.md)])
    rows.append(["", "Итого", "", f"ГКС {f(r.total_acid, 1)} м3; продавка {f(r.total_flush, 1)} м3",
                 "", f(r.total_acid + r.total_flush, 1), f(r.total_minutes, 0), ""])
    return head, rows


def table_results(r: CalcResult):
    pr = r.prod
    head = ["Параметр", "До ОПЗ", "После ОПЗ", "Разница"]
    rows = [
        ["Дебит жидкости, м3/сут", f(pr.q_liq_before, 1), f(pr.q_liq_after, 1), f(pr.dq_liq, 1)],
        ["Дебит нефти, т/сут", f(pr.q_oil_before, 2), f(pr.q_oil_after, 2), f(pr.dq_oil, 2)],
        ["Обводнённость, %", f(pr.water_cut, 1), f(pr.water_cut, 1), "0"],
        ["Забойное давление, атм", f(pr.p_bhp, 0), f(pr.p_bhp, 0), "0"],
        ["Коэффициент продуктивности, м3/сут/атм", f(pr.j_before, 3), f(pr.j_after, 3),
         f(pr.j_after - pr.j_before, 3)],
        ["Скин-фактор", f(pr.skin_before, 1), f(pr.skin_after, 1), f(pr.dskin, 1)],
        ["Дополнительная добыча нефти за 1 год, т", "", f(r.forecast.extra_oil_total, 0), ""],
    ]
    return head, rows


def forecast_method(r: CalcResult) -> str:
    fc = r.forecast
    base = f"{fc.decline * 100:.1f} %/мес ({fc.decline_source})"
    if fc.mode == "table":
        return ("Прогноз задан пользователем по месяцам (дебит жидкости в % от запускного, "
                "обводнённость и забойное давление). Дебит нефти рассчитан по дебиту жидкости и "
                "обводнённости; при изменении забойного давления дебит жидкости пересчитан "
                f"пропорционально депрессии. Добыча без ОПЗ падает по экспоненте с темпом {base}. "
                "Дополнительная добыча учитывается, пока дебит нефти выше базового.")
    return (f"Прогноз выполнен с экспоненциальным падением дебита {base}. Обводнённость и забойное "
            "давление приняты неизменными.")


def table_forecast(r: CalcResult):
    head = ["Месяц", "Qж, м3/сут", "Qн, т/сут", "Обв., %", "Рзаб, атм", "Qн без ОПЗ, т/сут",
            "Доп. добыча, т"]
    rows = [[str(x.month), f(x.q_liq, 1), f(x.q_oil, 2), f(x.water_cut, 1), f(x.p_bhp, 0),
             f(x.q_oil_base, 2), f(x.extra_oil, 0)] for x in r.forecast.rows]
    rows.append(["Итого", "", "", "", "", "", f(r.forecast.extra_oil_total, 0)])
    return head, rows


def table_pumping(r: CalcResult):
    head = ["Стадия", "Порт", "Рзаб нач., атм", "Рзаб кон., атм", "Ру макс., атм", "Ру кон., атм",
            "Скин кон."]
    rows = []
    for st, port, a, b in r.pumping.stage_bounds:
        pts = [p for p in r.pumping.points if p.stage == st and p.fluid != "—"]
        rows.append([str(st), f"МГРП{port}", f(pts[0].p_bh, 0), f(pts[-1].p_bh, 0),
                     f(max(p.p_wh for p in pts), 0), f(pts[-1].p_wh, 0), f(pts[-1].skin, 1)])
    return head, rows


def conclusions(p: Project, r: CalcResult) -> List[str]:
    pr = r.prod
    tr = treated(r.ports)
    pens = [x.penetration for x in tr]
    out = [
        f"Рассмотрен дизайн ОПЗ с закачкой {f(r.total_acid, 1)} м3 {p.design.acid_name} в {len(tr)} "
        f"муф{'ту' if len(tr) == 1 else 'ты' if len(tr) < 5 else 'т'} ГРП с продавкой "
        f"{p.design.flush_name.lower()} при расходе {f(p.design.rate)} м3/мин. Глубина проникновения "
        f"ГКС по закреплённой трещине составит {min(pens):.0f}–{max(pens):.0f} м.",
        f"Ожидаемый эффект: дебит жидкости {f(pr.q_liq_before, 1)} → {f(pr.q_liq_after, 1)} м3/сут, "
        f"дебит нефти {f(pr.q_oil_before, 2)} → {f(pr.q_oil_after, 2)} т/сут, скин-фактор "
        f"{pr.skin_before:+.1f} → {pr.skin_after:+.1f}, Кпрод {f(pr.j_before, 3)} → {f(pr.j_after, 3)} м3/сут/атм.",
        f"Дополнительная добыча нефти за {len(r.forecast.rows)} мес. — {f(r.forecast.extra_oil_total, 0)} т "
        + ("(прогноз задан по месяцам в табличном виде)." if r.forecast.mode == "table" else
           f"(темп падения {r.forecast.decline * 100:.1f} %/мес, {r.forecast.decline_source}).")
        + (f" Эффект от ОПЗ заканчивается на {r.forecast.effect_end_month}-м месяце (дебит нефти "
           "опускается ниже базового)." if r.forecast.effect_end_month else ""),
    ]
    if r.loss.loss_pct is not None:
        out.append(f"По данным входного контроля потеря продуктивности составляет {r.loss.loss_pct:.0f} % "
                   f"(Кпрод {f(r.loss.k_initial)} → {f(r.loss.k_current)} м3/сут/атм).")
    fp = p.reservoir.frac_pressure
    if fp > 0:
        margin = fp - r.pumping.max_p_bh
        if margin > 0:
            out.append(f"Максимальное расчётное забойное давление закачки {f(r.pumping.max_p_bh, 0)} атм "
                       f"ниже давления ГРП ({f(fp, 0)} атм) на {f(margin, 0)} атм.")
    out += [f"Внимание: {w}." for w in r.warnings]
    out += [
        "Рекомендуется перед ОПЗ провести тест на приемистость, по его результатам уточнить "
        "приемистость порта и выполнить редизайн режима закачки.",
        "При оценке сходимости прогнозных и фактических параметров после выхода скважины на режим "
        "необходимо выполнить пересчёт дебита нефти с учётом фактических данных закачки (расход, "
        "давления) и фактических значений забойного давления и обводнённости после ОПЗ.",
    ]
    return out
