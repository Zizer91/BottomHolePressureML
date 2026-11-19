"""Расчётное ядро AcidClean PRO.

Методика (подробно — в mopz/METHODOLOGY.md):

1. Трещина ГРП (по каждому порту, данные отчёта ГРП «факт»):
     Vтр   = 2 · Xf · H · w                      — объём закреплённой трещины, м3
     Vпор  = φпачки · Vтр                         — поровый объём пропантной пачки, м3
     Lпр   = Vгкс / (2 · φпачки · H · w)          — глубина проникновения ГКС (промытое
                                                    расстояние вдоль трещины), м
     η     = min(1, Lпр / Xf)                     — доля промытой полудлины
2. Скин:
     до ОПЗ  — по ГДИС, при отсутствии +0,5;
     после   — задан (по умолчанию −2) или рассчитан: S1 = S0 + (Sгрп − S0) · η,
               Sгрп — «идеальный геометрический» скин после ГРП из отчёта ГРП.
3. Формула Дюпюи, нормированная на фактический режим:
     Кпрод0 = Qж0 / (Рпл − Рзаб)
     Кпрод1 = Кпрод0 · (ln(Rк/rc) + S0) / (ln(Rк/rc) + S1)
     Qж1 = Кпрод1 · (Рпл − Рзаб); обводнённость и Рзаб не меняются;
     Qн1 = Qн0 · Qж1 / Qж0.
4. Прогноз на 12 мес. — экспоненциальное падение с темпом D (%/мес), по умолчанию
   оценивается по истории добычи нефти; доп. добыча = Σ (Qн1 − Qн0)·e^(−D·t)·дни.
5. Режим закачки: забойное давление Рзаб = Рпл + q / J(t),
     J(t) = J0 · (ln(Rк/rc) + S0) / (ln(Rк/rc) + S(t)), J0 — приемистость порта до ОПЗ;
   устьевое Ру = Рзаб − Ргидр + Ртр (трение по Дарси–Вейсбаху, Блазиус).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

from .models import Port, Project

G = 9.80665
ATM = 101325.0
DAYS_IN_MONTH = 30.4


# ---------------------------------------------------------------------------
# Инклинометрия
# ---------------------------------------------------------------------------
def survey_tvd(project: Project) -> Tuple[List[float], List[float]]:
    """MD → TVD (от ротора) методом минимальной кривизны."""
    rows = sorted(project.survey, key=lambda r: r.md)
    if len(rows) < 2:
        return [], []
    md = [rows[0].md]
    tvd = [rows[0].md if rows[0].incl == 0 else rows[0].md * math.cos(math.radians(rows[0].incl))]
    for a, b in zip(rows[:-1], rows[1:]):
        dmd = b.md - a.md
        if dmd <= 0:
            continue
        i1, i2 = math.radians(a.incl), math.radians(b.incl)
        a1, a2 = math.radians(a.azim), math.radians(b.azim)
        cos_dl = math.cos(i2 - i1) - math.sin(i1) * math.sin(i2) * (1 - math.cos(a2 - a1))
        dl = math.acos(max(-1.0, min(1.0, cos_dl)))
        rf = 1.0 if dl < 1e-9 else 2 / dl * math.tan(dl / 2)
        md.append(b.md)
        tvd.append(tvd[-1] + dmd / 2 * (math.cos(i1) + math.cos(i2)) * rf)
    return md, tvd


def make_tvd_func(project: Project):
    md_s, tvd_s = survey_tvd(project)
    if md_s:
        def f(md: float) -> float:
            if md <= md_s[0]:
                return tvd_s[0] * md / md_s[0] if md_s[0] else md
            if md >= md_s[-1]:
                return tvd_s[-1]
            lo, hi = 0, len(md_s) - 1
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if md_s[mid] <= md:
                    lo = mid
                else:
                    hi = mid
            t = (md - md_s[lo]) / (md_s[hi] - md_s[lo])
            return tvd_s[lo] + t * (tvd_s[hi] - tvd_s[lo])
        return f

    res_tvd = project.construction.reservoir_tvd
    max_md = max([p.md for p in project.ports] + [1.0])

    def g(md: float) -> float:
        if res_tvd <= 0:
            return md
        return min(res_tvd, md * res_tvd / max_md)
    return g


# ---------------------------------------------------------------------------
# Трещины
# ---------------------------------------------------------------------------
@dataclass
class PortResult:
    port: Port
    tvd: float
    frac_volume: float
    pore_volume: float
    acid_volume: float
    flush_volume: float
    penetration: float
    fraction: float
    skin_after: float


def port_acid_volume(project: Project, port: Port, pore_volume: float) -> float:
    if port.acid_volume is not None:
        return port.acid_volume
    d = project.design
    if d.acid_mode == "pore":
        # округление до 0,5 м3 вверх
        return math.ceil(d.pore_fraction * pore_volume * 2) / 2
    return d.acid_volume


def fracture_results(project: Project) -> List[PortResult]:
    d = project.design
    tvd = make_tvd_func(project)
    s0 = project.regime.skin_before
    out = []
    for p in project.ports:
        w = p.width_mm / 1000.0
        vfr = 2 * p.xf * p.height * w
        vpore = d.pack_porosity * vfr
        vac = port_acid_volume(project, p, vpore) if p.treat else 0.0
        denom = 2 * d.pack_porosity * p.height * w
        pen = vac / denom if denom > 0 else 0.0
        frac = min(1.0, pen / p.xf) if p.xf > 0 else 0.0
        if d.skin_after_mode == "calc":
            s1 = s0 + (p.skin_frac - s0) * frac
        else:
            s1 = d.skin_after
        if not p.treat:
            s1 = s0
        out.append(PortResult(
            port=p, tvd=tvd(p.md), frac_volume=vfr, pore_volume=vpore,
            acid_volume=vac,
            flush_volume=(p.flush_volume if p.flush_volume is not None else d.flush_volume) if p.treat else 0.0,
            penetration=min(pen, p.xf) if p.xf > 0 else pen, fraction=frac, skin_after=s1))
    return out


def treated(results: List[PortResult]) -> List[PortResult]:
    """Обрабатываемые порты в порядке закачки — от забоя к устью (по убыванию MD)."""
    return sorted([r for r in results if r.port.treat], key=lambda r: -r.port.md)


# ---------------------------------------------------------------------------
# Продуктивность (Дюпюи)
# ---------------------------------------------------------------------------
@dataclass
class ProductivityResult:
    ln_term: float
    skin_before: float
    skin_after: float
    j_before: float
    j_after: float
    q_liq_before: float
    q_liq_after: float
    q_oil_before: float
    q_oil_after: float
    water_cut: float
    p_bhp: float

    @property
    def dq_liq(self):
        return self.q_liq_after - self.q_liq_before

    @property
    def dq_oil(self):
        return self.q_oil_after - self.q_oil_before

    @property
    def dskin(self):
        return self.skin_before - self.skin_after


def ln_term(project: Project) -> float:
    r = project.reservoir
    if r.drainage_radius <= 0 or r.well_radius <= 0 or r.drainage_radius <= r.well_radius:
        raise ValueError("Rк и rc должны быть > 0, Rк > rc")
    return math.log(r.drainage_radius / r.well_radius)


def productivity(project: Project, results: Optional[List[PortResult]] = None) -> ProductivityResult:
    if results is None:
        results = fracture_results(project)
    reg, res = project.regime, project.reservoir
    dp = res.p_res - reg.p_bhp
    if dp <= 0:
        raise ValueError("Пластовое давление должно быть больше забойного")
    lt = ln_term(project)
    s0 = reg.skin_before
    tr = treated(results)
    s1 = sum(r.skin_after for r in tr) / len(tr) if tr else s0
    if lt + s1 <= 0.1:
        raise ValueError("ln(Rк/rc) + S после ОПЗ ≤ 0 — проверьте Rк, rc и скин")
    j0 = reg.q_liq / dp
    j1 = j0 * (lt + s0) / (lt + s1)
    q1 = j1 * dp
    qo1 = reg.q_oil * q1 / reg.q_liq if reg.q_liq > 0 else 0.0
    return ProductivityResult(lt, s0, s1, j0, j1, reg.q_liq, q1, reg.q_oil, qo1,
                              reg.water_cut, reg.p_bhp)


# ---------------------------------------------------------------------------
# История и потеря продуктивности
# ---------------------------------------------------------------------------
def parse_date(s) -> Optional[datetime]:
    if isinstance(s, datetime):
        return s
    if not s:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d.%m.%y", "%m.%Y"):
        try:
            return datetime.strptime(str(s).strip(), fmt)
        except ValueError:
            pass
    return None


@dataclass
class HistoryPoint:
    date: datetime
    p_bhp: Optional[float]
    q_oil: Optional[float]
    q_liq: Optional[float]
    water_cut: Optional[float]
    q_liq_m3: Optional[float]
    kprod: Optional[float]
    p_res: Optional[float] = None


def history_points(project: Project) -> List[HistoryPoint]:
    res = project.reservoir
    rows = [(parse_date(h.date), h) for h in project.history]
    rows = sorted([(d, h) for d, h in rows if d is not None], key=lambda x: x[0])
    d_first = rows[0][0] if rows else None
    d_last = rows[-1][0] if rows else None
    out = []
    for d, h in rows:
        p_res = h.p_res
        if p_res is None:
            if res.p_res_initial > 0 and d_last != d_first:
                frac = (d - d_first).days / (d_last - d_first).days
                p_res = res.p_res_initial + (res.p_res - res.p_res_initial) * frac
            else:
                p_res = res.p_res
        qm3 = None
        if h.q_liq is not None and h.q_oil is not None and h.q_liq > 0:
            qw = max(0.0, h.q_liq - h.q_oil)
            qm3 = h.q_oil / res.oil_density + qw / res.water_density
        kp = None
        if qm3 and h.p_bhp is not None and p_res > h.p_bhp:
            kp = qm3 / (p_res - h.p_bhp)
        out.append(HistoryPoint(d, h.p_bhp, h.q_oil, h.q_liq, h.water_cut, qm3, kp, p_res))
    return out


@dataclass
class ProductivityLoss:
    k_initial: Optional[float]
    k_current: Optional[float]
    loss_pct: Optional[float]


def productivity_loss(points: List[HistoryPoint], k_current: Optional[float] = None) -> ProductivityLoss:
    ks = [p.kprod for p in points if p.kprod]
    if not ks:
        return ProductivityLoss(None, k_current, None)
    first = sorted(ks[:3])
    k_init = first[len(first) // 2]   # медиана первых трёх замеров (отсекаем выбросы освоения)
    k_cur = k_current if k_current is not None else ks[-1]
    return ProductivityLoss(k_init, k_cur, (1 - k_cur / k_init) * 100 if k_init else None)


DEFAULT_DECLINE = 0.02


def estimate_decline(points: List[HistoryPoint], months: int = 12) -> float:
    """Темп падения дебита нефти, доли/мес, по экспоненте на последних N мес.

    Возвращает 0, если падение по истории не выявлено или данных мало."""
    pts = [p for p in points if p.q_oil and p.q_oil > 0][-months:]
    if len(pts) < 4:
        return 0.0
    t0 = pts[0].date
    xs = [(p.date - t0).days / DAYS_IN_MONTH for p in pts]
    ys = [math.log(p.q_oil) for p in pts]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return 0.0
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return min(0.15, max(0.0, -slope))


# ---------------------------------------------------------------------------
# Прогноз на год
# ---------------------------------------------------------------------------
@dataclass
class ForecastRow:
    month: int
    q_liq: float
    q_oil: float
    water_cut: float
    p_bhp: float
    q_oil_base: float
    extra_oil: float     # т за месяц


@dataclass
class Forecast:
    decline: float       # доли/мес
    decline_source: str = ""
    rows: List[ForecastRow] = field(default_factory=list)

    @property
    def extra_oil_total(self):
        return sum(r.extra_oil for r in self.rows)


def forecast(project: Project, prod: ProductivityResult, points=None) -> Forecast:
    d = project.design
    if d.forecast_decline and d.forecast_decline > 0:
        dec = d.forecast_decline / 100.0
        src = "задан пользователем"
    else:
        dec = estimate_decline(points if points is not None else history_points(project))
        src = "оценён по истории добычи нефти (экспонента, последние 12 мес.)"
        if dec < 0.005:
            dec = DEFAULT_DECLINE
            src = "по истории падение не выявлено — принят по умолчанию"
    fc = Forecast(dec, src)
    for m in range(1, int(d.forecast_months) + 1):
        f_mid = math.exp(-dec * (m - 0.5))
        f_end = math.exp(-dec * (m - 1))
        ql = prod.q_liq_after * f_end
        qo = prod.q_oil_after * f_end
        qob = prod.q_oil_before * f_end
        extra = (prod.q_oil_after - prod.q_oil_before) * f_mid * DAYS_IN_MONTH
        fc.rows.append(ForecastRow(m, ql, qo, prod.water_cut, prod.p_bhp, qob, extra))
    return fc


# ---------------------------------------------------------------------------
# План закачки и режим закачки
# ---------------------------------------------------------------------------
@dataclass
class PlanRow:
    n: int
    stage: int
    port_number: int
    kind: str           # «Кислота» / «Продавка»
    fluid: str
    rate: float
    volume: float
    minutes: float
    md: float


def injection_plan(project: Project, results: Optional[List[PortResult]] = None) -> List[PlanRow]:
    if results is None:
        results = fracture_results(project)
    d = project.design
    rows: List[PlanRow] = []
    n = 0
    for st, r in enumerate(treated(results), start=1):
        for kind, fluid, vol in (("Кислота", d.acid_name, r.acid_volume),
                                 ("Продавка", d.flush_name, r.flush_volume)):
            if vol <= 0:
                continue
            n += 1
            rows.append(PlanRow(n, st, r.port.number, kind, fluid, d.rate, vol,
                                vol / d.rate if d.rate > 0 else 0.0, r.port.md))
    return rows


def friction_loss(rate_m3_min: float, d_id_mm: float, length: float,
                  density: float, visc_cp: float) -> float:
    """Потери на трение в трубе, атм (Дарси–Вейсбах, Блазиус / Пуазейль)."""
    if rate_m3_min <= 0 or length <= 0:
        return 0.0
    dm = d_id_mm / 1000.0
    area = math.pi * dm ** 2 / 4
    v = rate_m3_min / 60.0 / area
    rho = density * 1000.0
    mu = max(visc_cp, 0.01) / 1000.0
    re = rho * v * dm / mu
    lam = 64 / re if re < 2300 else 0.3164 / re ** 0.25
    return lam * length / dm * rho * v * v / 2 / ATM


@dataclass
class PumpPoint:
    t: float            # мин от начала
    stage: int
    rate: float
    p_bh: float
    p_wh: float
    skin: float
    fluid: str          # жидкость, поступающая в пласт
    acid_in: float      # м3 ГКС, вошедшей в пласт на текущем порту


@dataclass
class PumpSimulation:
    points: List[PumpPoint]
    stage_bounds: List[Tuple[int, int, float, float]]   # (стадия, порт, t_нач, t_кон)
    tubing_volumes: List[float]

    @property
    def max_p_bh(self):
        return max((p.p_bh for p in self.points), default=0.0)

    @property
    def max_p_wh(self):
        return max((p.p_wh for p in self.points), default=0.0)


def simulate_pumping(project: Project, results: Optional[List[PortResult]] = None,
                     dt: float = 0.25) -> PumpSimulation:
    if results is None:
        results = fracture_results(project)
    d, c, res = project.design, project.construction, project.reservoir
    tvd = make_tvd_func(project)
    lt = ln_term(project)
    s0 = project.regime.skin_before
    area = math.pi * (c.tubing_id / 1000.0) ** 2 / 4
    props = {"acid": (d.acid_density, d.acid_visc), "flush": (d.flush_density, 1.0)}
    pts: List[PumpPoint] = []
    bounds = []
    tub_vols = []
    t = 0.0
    q = d.rate
    q_day = q * 1440.0
    for st, r in enumerate(treated(results), start=1):
        md_shoe = r.port.md
        vt = area * md_shoe
        tub_vols.append(vt)
        # содержимое НКТ сверху вниз: [(жидкость, объём)]
        tubing = [("flush", vt)]
        pumped_plan = [("acid", r.acid_volume), ("flush", r.flush_volume)]
        acid_in = 0.0
        t_start = t
        for fluid, vol in pumped_plan:
            remaining = vol
            while remaining > 1e-9:
                dv = min(q * dt, remaining)
                remaining -= dv
                # закачали dv сверху, вытеснили dv снизу
                tubing.insert(0, (fluid, dv))
                out = dv
                while out > 1e-12 and tubing:
                    f_last, v_last = tubing[-1]
                    take = min(v_last, out)
                    if f_last == "acid":
                        acid_in += take
                    out -= take
                    if v_last - take <= 1e-12:
                        tubing.pop()
                    else:
                        tubing[-1] = (f_last, v_last - take)
                # слить соседние одинаковые сегменты
                merged = []
                for f_, v_ in tubing:
                    if merged and merged[-1][0] == f_:
                        merged[-1] = (f_, merged[-1][1] + v_)
                    else:
                        merged.append((f_, v_))
                tubing = merged
                t += dv / q
                # гидростатика и трение по сегментам
                p_h = 0.0
                p_f = 0.0
                md_top = 0.0
                for f_, v_ in tubing:
                    seg = v_ / area
                    md_bot = min(md_shoe, md_top + seg)
                    rho, mu = props[f_]
                    p_h += rho * 1000 * G * (tvd(md_bot) - tvd(md_top)) / ATM
                    p_f += friction_loss(q, c.tubing_id, md_bot - md_top, rho, mu)
                    md_top = md_bot
                p_f *= d.friction_factor
                frac_acid = min(1.0, acid_in / r.acid_volume) if r.acid_volume > 0 else 1.0
                skin = s0 + (r.skin_after - s0) * math.sqrt(frac_acid)
                j = d.injectivity * (lt + s0) / max(0.1, lt + skin)
                p_bh = res.p_res + q_day / j if j > 0 else res.p_res
                p_wh = max(0.0, p_bh - p_h + p_f)
                entering = "ГКС" if tubing and tubing[-1][0] == "acid" else "Продавка"
                pts.append(PumpPoint(t, st, q, p_bh, p_wh, skin, entering, acid_in))
        bounds.append((st, r.port.number, t_start, t))
        if d.gap_minutes > 0:
            last = pts[-1]
            for k in (0.0, d.gap_minutes):
                pts.append(PumpPoint(t + k, st, 0.0, res.p_res,
                                     max(0.0, res.p_res - (last.p_bh - last.p_wh)),
                                     last.skin, "—", acid_in))
            t += d.gap_minutes
    return PumpSimulation(pts, bounds, tub_vols)


# ---------------------------------------------------------------------------
# Сводный расчёт и проверки
# ---------------------------------------------------------------------------
@dataclass
class CalcResult:
    ports: List[PortResult]
    prod: ProductivityResult
    history: List[HistoryPoint]
    loss: ProductivityLoss
    forecast: Forecast
    plan: List[PlanRow]
    pumping: PumpSimulation
    warnings: List[str]

    @property
    def total_acid(self):
        return sum(r.acid_volume for r in self.ports if r.port.treat)

    @property
    def total_flush(self):
        return sum(r.flush_volume for r in self.ports if r.port.treat)

    @property
    def total_height(self):
        return sum(r.port.height for r in self.ports if r.port.treat)

    @property
    def total_minutes(self):
        return sum(p.minutes for p in self.plan)


def validate(project: Project) -> List[str]:
    errs = []
    if not project.ports:
        errs.append("Не заданы муфты ГРП")
    if not any(p.treat for p in project.ports):
        errs.append("Не выбран ни один порт для обработки")
    for p in project.ports:
        if p.treat and (p.xf <= 0 or p.height <= 0 or p.width_mm <= 0):
            errs.append(f"Порт {p.number}: не заданы Xf, H или ширина трещины")
    r, g = project.reservoir, project.regime
    if r.p_res <= 0:
        errs.append("Не задано пластовое давление")
    if g.q_liq <= 0:
        errs.append("Не задан дебит жидкости до ОПЗ")
    if g.p_bhp <= 0 or g.p_bhp >= r.p_res:
        errs.append("Забойное давление должно быть > 0 и меньше пластового")
    if project.design.rate <= 0:
        errs.append("Не задан расход закачки")
    if project.construction.tubing_id <= 0:
        errs.append("Не задан внутренний диаметр НКТ")
    return errs


def run(project: Project) -> CalcResult:
    errs = validate(project)
    if errs:
        raise ValueError("\n".join(errs))
    ports = fracture_results(project)
    prod = productivity(project, ports)
    hist = history_points(project)
    loss = productivity_loss(hist)
    fc = forecast(project, prod, hist)
    plan = injection_plan(project, ports)
    pump = simulate_pumping(project, ports)
    warns = []
    c = project.construction
    for r, vt in zip(treated(ports), pump.tubing_volumes):
        if r.flush_volume < vt:
            warns.append(f"Порт {r.port.number}: объём продавки {r.flush_volume:.1f} м3 меньше объёма "
                         f"НКТ {vt:.1f} м3 — часть ГКС останется в НКТ")
        if c.funnel_md and r.port.md > c.funnel_md:
            warns.append(f"Порт {r.port.number} (MD {r.port.md:.1f} м) ниже полированной воронки "
                         f"({c.funnel_md:.1f} м)")
        if r.fraction >= 1.0:
            warns.append(f"Порт {r.port.number}: объём ГКС превышает поровый объём трещины "
                         f"({r.pore_volume:.1f} м3)")
    fp = project.reservoir.frac_pressure
    if fp > 0 and pump.max_p_bh >= fp:
        warns.append(f"Максимальное забойное давление закачки {pump.max_p_bh:.0f} атм ≥ давления ГРП "
                     f"{fp:.0f} атм — снизьте расход")
    return CalcResult(ports, prod, hist, loss, fc, plan, pump, warns)
