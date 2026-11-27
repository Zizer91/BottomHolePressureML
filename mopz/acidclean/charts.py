"""Графики отчёта (matplotlib). Каждая функция возвращает Figure."""
from __future__ import annotations

import math
from dataclasses import replace

import matplotlib

matplotlib.use("Agg")
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from .calc import CalcResult, interp, parse_date, survey_trajectory, treated  # noqa: E402

GREY = "#6B6B6B"

# Настраиваемые цвета: ключ -> (подпись для пользователя, цвет по умолчанию)
PALETTE_SPEC = {
    "LIQ": ("Дебит жидкости (Qж)", "#2C7FB8"),
    "OIL": ("Дебит нефти (Qн)", "#7A4E1D"),
    "BHP": ("Забойное / пластовое давление (история, прогноз)", "#9B1B30"),
    "WC": ("Обводнённость", "#6B6B6B"),
    "KPROD": ("Коэффициент продуктивности", "#000000"),
    "BH_INJ": ("Забойное давление закачки", "#000000"),
    "WH_INJ": ("Устьевое давление закачки", "#000000"),
    "FRAC_P": ("Давление ГРП", "#9B1B30"),
    "RATE": ("Расход закачки", "#3BAA5C"),
    "ACID": ("ГКС / промытая зона трещины", "#3BAA5C"),
    "FLUSH": ("Продавка (тех. жидкость)", "#5B7FD6"),
    "PROP": ("Закреплённая трещина (пропант)", "#C9B88A"),
    "PORT": ("Муфта ГРП (обрабатывается)", "#9B1B30"),
    "PORT_OFF": ("Муфта ГРП (не обрабатывается)", "#6B6B6B"),
    "WELL": ("Ствол скважины", "#000000"),
    "FUNNEL": ("Полированная воронка", "#2C7FB8"),
    "ACCENT": ("Выделение (потеря продуктивности)", "#9B1B30"),
}
PALETTE = {k: v[1] for k, v in PALETTE_SPEC.items()}


def set_palette(colors: dict) -> None:
    """Применить пользовательские цвета (неизвестные ключи и пустые значения игнорируются)."""
    PALETTE.update({k: v for k, v in (colors or {}).items() if k in PALETTE_SPEC and v})


def reset_palette() -> None:
    PALETTE.update({k: v[1] for k, v in PALETTE_SPEC.items()})


def C(key: str) -> str:
    return PALETTE[key]


matplotlib.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "axes.spines.top": False,
})


def _fig(w=8.0, h=4.5):
    return Figure(figsize=(w, h), dpi=110, layout="constrained")


def _nice_step(span):
    for s in (5, 10, 20, 25, 50, 100):
        if span / s <= 12:
            return s
    return 200


# ---------------------------------------------------------------------------
def fracture_detail(res: CalcResult) -> Figure:
    """Прохождение ГКС по трещине каждого порта с разлиновкой расстояния."""
    tr = treated(res.ports)
    fig = _fig(8, 0.55 * len(tr) + 1.6)
    ax = fig.add_subplot()
    xmax = max(r.port.xf for r in tr) if tr else 1
    for i, r in enumerate(tr):
        y = len(tr) - 1 - i
        ax.barh(y, r.port.xf, color=C("PROP"), edgecolor=GREY, height=0.55,
                label="Закреплённая трещина (пропант)")
        ax.barh(y, r.penetration, color=C("ACID"), edgecolor=GREY, height=0.55, label="Промыто ГКС")
        ax.text(r.penetration, y, f" {r.penetration:.1f} м", va="center", ha="left",
                fontsize=8, color="black")
        ax.text(r.port.xf + xmax * 0.01, y, f"Xf {r.port.xf:.1f}", va="center", fontsize=8,
                color=GREY)
    labels = [f"Ст. {i + 1} · МГРП{r.port.number}" for i, r in enumerate(tr)]
    ax.set_yticks(range(len(tr)))
    ax.set_yticklabels(list(reversed(labels)))
    step = _nice_step(xmax)
    ax.set_xticks(range(0, int(xmax * 1.15) + step, step))
    ax.set_xlim(0, xmax * 1.15)
    ax.grid(axis="x", which="major", alpha=0.6, linestyle="--")
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Расстояние от ствола скважины вдоль трещины (полудлина), м")
    ax.set_title("Прохождение ГКС по закреплённой трещине ГРП")
    ax.legend(handles=[Patch(color=C("ACID"), label="Промыто ГКС"),
                       Patch(color=C("PROP"), label="Закреплённая трещина (пропант)")],
              loc="upper center", bbox_to_anchor=(0.5, -0.12 - 0.3 / max(1, len(tr))), ncol=2,
              fontsize=8, frameon=False)
    return fig


def fracture_plan(res: CalcResult) -> Figure:
    """Вид в плане: горизонтальный ствол, трещины ±Xf и зона промывки ±Lпр."""
    fig = _fig(8, 4.2)
    ax = fig.add_subplot()
    ports = res.ports
    if not ports:
        return fig
    mds = [r.port.md for r in ports]
    ax.plot([min(mds) - 60, max(mds) + 60], [0, 0], color=C("WELL"), lw=2.5, label="Ствол (хвостовик)")
    for r in ports:
        x = r.port.md
        ax.plot([x, x], [-r.port.xf, r.port.xf], color=C("PROP"), lw=7, solid_capstyle="butt",
                label="Закреплённая трещина")
        if r.port.treat:
            ax.plot([x, x], [-r.penetration, r.penetration], color=C("ACID"), lw=7, solid_capstyle="butt",
                    label="Промыто ГКС")
        ax.text(x, r.port.xf + 8, f"МГРП{r.port.number}", ha="center", fontsize=8)
        ax.text(x, -r.port.xf - 8, f"{x:.0f}", ha="center", va="top", fontsize=7, color=GREY)
    ymax = max(r.port.xf for r in ports)
    step = _nice_step(ymax)
    ax.set_yticks(range(-int(ymax // step + 1) * step, int(ymax // step + 2) * step, step))
    ax.set_ylim(-ymax - 35, ymax + 25)
    ax.set_xlabel("Глубина по стволу (MD), м")
    ax.set_ylabel("Расстояние от ствола, м")
    ax.set_title("Схема трещин ГРП и зоны промывки ГКС (вид в плане)")
    ax.invert_xaxis()
    ax.legend(handles=[Patch(color=C("ACID"), label="Промыто ГКС"),
                       Patch(color=C("PROP"), label="Закреплённая трещина"),
                       Patch(color=C("WELL"), label="Ствол (хвостовик)")],
              loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=3, fontsize=8, frameon=False)
    return fig


# ---------------------------------------------------------------------------
def history_chart(res: CalcResult) -> Figure:
    """Диаграмма работы скважины (входной контроль) с потерей продуктивности."""
    pts = res.history
    fig = _fig(8, 6)
    ax1, ax3 = fig.subplots(2, 1, sharex=True)
    if not pts:
        ax1.text(0.5, 0.5, "История эксплуатации не загружена", ha="center", transform=ax1.transAxes)
        return fig
    d = [p.date for p in pts]
    ax1.plot(d, [p.q_liq for p in pts], "-o", ms=3, color=C("LIQ"), label="Qж, т/сут")
    ax1.plot(d, [p.q_oil for p in pts], "-o", ms=3, color=C("OIL"), label="Qн, т/сут")
    ax1.set_ylabel("Дебит, т/сут")
    ax2 = ax1.twinx()
    ax2.plot(d, [p.water_cut for p in pts], "--", color=C("WC"), label="Обв., %")
    ax2.set_ylabel("Обводнённость, %")
    ax2.set_ylim(0, 100)
    ax2.grid(False)
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8)
    ax1.set_title("Диаграмма работы скважины (входной контроль)")

    ax3.plot(d, [p.p_bhp for p in pts], "-s", ms=3, color=C("BHP"), label="Рзаб, атм")
    if any(p.p_res for p in pts):
        ax3.plot(d, [p.p_res for p in pts], ":", color=C("BHP"), alpha=0.6, label="Рпл, атм")
    ax3.set_ylabel("Давление, атм")
    ax4 = ax3.twinx()
    ax4.plot(d, [p.kprod for p in pts], "-^", ms=3, color=C("KPROD"), label="Кпрод, м3/сут/атм")
    ax4.set_ylabel("Кпрод, м3/сут/атм")
    ax4.grid(False)
    loss = res.loss
    if loss.loss_pct is not None:
        ax4.axhline(loss.k_initial, color=C("KPROD"), lw=0.8, ls="--")
        ax4.text(d[0], loss.k_initial, f"  Кпрод нач. {loss.k_initial:.2f}", va="bottom", fontsize=8)
        ax3.text(0.5, 0.92, f"Кпрод: {loss.k_initial:.2f} → {loss.k_current:.2f} м3/сут/атм, "
                 f"потеря продуктивности {loss.loss_pct:.0f} %", transform=ax3.transAxes,
                 ha="center", va="top", fontsize=9, color=C("ACCENT"), weight="bold",
                 bbox=dict(facecolor="white", edgecolor=C("ACCENT"), alpha=0.9))
        ks = [p.kprod for p in pts if p.kprod]
        if max(ks) > 4 * loss.k_initial:
            ax4.set_ylim(0, loss.k_initial * 1.6)
    h3, l3 = ax3.get_legend_handles_labels()
    h4, l4 = ax4.get_legend_handles_labels()
    ax3.legend(h3 + h4, l3 + l4, loc="center right", fontsize=8)
    fig.autofmt_xdate()
    return fig


def forecast_chart(res: CalcResult) -> Figure:
    fc, prod = res.forecast, res.prod
    fig = _fig(8, 4.6)
    ax = fig.add_subplot()
    m = [0] + [r.month for r in fc.rows]
    ql = [prod.q_liq_before] + [r.q_liq for r in fc.rows]
    qo = [prod.q_oil_before] + [r.q_oil for r in fc.rows]
    qb = [prod.q_oil_before] + [r.q_oil_base for r in fc.rows]
    ax.plot(m, ql, "-o", ms=4, color=C("LIQ"), label="Qж, м3/сут")
    ax.plot(m, qo, "-o", ms=4, color=C("OIL"), label="Qн, т/сут")
    ax.plot(m, qb, ":", color=C("OIL"), alpha=0.7, label="Qн без ОПЗ, т/сут")
    ax.fill_between(m[1:], qb[1:], qo[1:], color=C("OIL"), alpha=0.12)
    ax.set_xlabel("Месяц после ОПЗ (0 — до ОПЗ)")
    ax.set_ylabel("Дебит")
    ax.set_ylim(bottom=0)
    ax.set_xticks(m)
    ax2 = ax.twinx()
    wc = [prod.water_cut] + [r.water_cut for r in fc.rows]
    pb = [prod.p_bhp] + [r.p_bhp for r in fc.rows]
    ax2.plot(m, wc, "--", color=C("WC"), label="Обв., %")
    ax2.plot(m, pb, "-", color=C("BHP"), label="Рзаб, атм")
    ax2.set_ylabel("Обводнённость, % / Рзаб, атм")
    ax2.set_ylim(0, max(100, max(pb) * 1.3))
    ax2.grid(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8)
    ax.set_title(f"Планируемые параметры работы на {len(fc.rows)} мес. "
                 f"(доп. добыча {fc.extra_oil_total:.0f} т)")
    return fig


def _shade(ax, pts):
    if not pts:
        return
    start = pts[0].t
    cur = pts[0].fluid
    for a, b in zip(pts[:-1], pts[1:]):
        if b.fluid != cur:
            ax.axvspan(start, a.t, color=C("ACID") if cur == "ГКС" else C("FLUSH"), alpha=0.18, lw=0)
            start, cur = a.t, b.fluid
    ax.axvspan(start, pts[-1].t, color=C("ACID") if cur == "ГКС" else C("FLUSH"), alpha=0.18, lw=0)


def pumping_chart(res: CalcResult, frac_pressure: float, stage=None) -> Figure:
    pts = res.pumping.points
    title = "Режим технологических закачек. Все стадии"
    if stage is not None:
        pts = [p for p in pts if p.stage == stage]
        t0 = pts[0].t - 0.25 if pts else 0
        title = f"Режим закачки. Стадия {stage}"
    else:
        t0 = 0
    fig = _fig(8, 4.5)
    ax = fig.add_subplot()
    if not pts:
        return fig
    t = [p.t - t0 for p in pts]
    pumping = [p for p in pts if p.fluid != "—"]
    _shade(ax, [replace(p, t=p.t - t0) for p in pumping])
    ax.plot(t, [p.p_bh for p in pts], "--", color=C("BH_INJ"), label="Забойное давление")
    ax.plot(t, [p.p_wh for p in pts], "-.", color=C("WH_INJ"), label="Устьевое давление")
    if frac_pressure > 0:
        ax.axhline(frac_pressure, color=C("FRAC_P"), lw=1.2, label="Давление ГРП")
    ax.set_ylim(0, max(frac_pressure, max(p.p_bh for p in pts)) * 1.25)
    ax.set_ylabel("Давление, атм")
    ax.set_xlabel("Время, мин")
    ax2 = ax.twinx()
    ax2.step(t, [p.rate for p in pts], where="post", color=C("RATE"), lw=1.5, label="Расход")
    ax2.set_ylim(0, max(p.rate for p in pts) * 2 + 0.01)
    ax2.set_ylabel("Расход, м3/мин")
    ax2.grid(False)
    if stage is None:
        for st, port, a, b in res.pumping.stage_bounds:
            ax.text((a + b) / 2, ax.get_ylim()[1] * 0.95, f"Ст.{st}\nМГРП{port}", ha="center",
                    va="top", fontsize=7)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    extra = [Patch(color=C("ACID"), alpha=0.3, label="В пласт поступает ГКС"),
             Patch(color=C("FLUSH"), alpha=0.3, label="В пласт поступает тех. жидкость")]
    ax.legend(h1 + h2 + extra, l1 + l2 + [e.get_label() for e in extra], loc="lower right",
              fontsize=7, ncol=2)
    ax.set_title(title)
    return fig


def skin_chart(res: CalcResult) -> Figure:
    fig = _fig(8, 4.2)
    ax = fig.add_subplot()
    s0 = res.prod.skin_before
    for i, r in enumerate(treated(res.ports), start=1):
        if r.acid_volume <= 0:
            continue
        v = [r.acid_volume * k / 50 for k in range(51)]
        s = [s0 + (r.skin_after - s0) * math.sqrt(x / r.acid_volume) for x in v]
        v.append(r.acid_volume + r.flush_volume)
        s.append(r.skin_after)
        ax.plot(v, s, label=f"Ст.{i} МГРП{r.port.number}: {s0:+.1f} → {r.skin_after:+.1f}")
    vmax = max((r.acid_volume for r in res.ports if r.port.treat), default=0)
    ax.axvspan(0, vmax, color=C("ACID"), alpha=0.12)
    ax.axvspan(vmax, vmax + max((r.flush_volume for r in res.ports if r.port.treat), default=0),
               color=C("FLUSH"), alpha=0.12)
    ax.set_xlabel("Объём закачки в пласт, м3")
    ax.set_ylabel("Скин-фактор")
    ax.set_title("Изменение скин-фактора по зонам обработки")
    ax.legend(fontsize=7)
    return fig


def work_chart(history, w=8.0, h=5.5) -> Figure:
    """График работы скважины по таблице истории: Qн, Qж — основная ось; Рзаб и обв. — доп. оси."""
    fig = _fig(w, h)
    ax = fig.add_subplot()
    rows = sorted([(parse_date(r.date), r) for r in history if parse_date(r.date)], key=lambda x: x[0])
    if not rows:
        ax.axis("off")
        ax.text(0.5, 0.5, "Нет данных истории\n(нужны дата и хотя бы один параметр)", ha="center",
                va="center", transform=ax.transAxes, color=GREY)
        return fig
    d = [x[0] for x in rows]

    def col(attr):
        return [getattr(r, attr) if getattr(r, attr) is not None else float("nan") for _, r in rows]

    l1 = ax.plot(d, col("q_liq"), "-o", ms=3, color=C("LIQ"), label="Qж, т/сут")
    l2 = ax.plot(d, col("q_oil"), "-o", ms=3, color=C("OIL"), label="Qн, т/сут")
    ax.set_ylabel("Дебит, т/сут")
    ax.set_ylim(bottom=0)
    ax_p = ax.twinx()
    l3 = ax_p.plot(d, col("p_bhp"), "-s", ms=3, color=C("BHP"), label="Рзаб, атм")
    pr = col("p_res")
    l5 = []
    if any(v == v for v in pr):
        l5 = ax_p.plot(d, pr, ":", color=C("BHP"), alpha=0.6, label="Рпл, атм")
    ax_p.set_ylabel("Рзаб, атм", color=C("BHP"))
    ax_p.tick_params(axis="y", colors=C("BHP"))
    ax_p.set_ylim(bottom=0)
    ax_p.grid(False)
    ax_w = ax.twinx()
    ax_w.spines["right"].set_position(("axes", 1.12))
    ax_w.spines["right"].set_visible(True)
    l4 = ax_w.plot(d, col("water_cut"), "--", color=C("WC"), label="Обв., %")
    ax_w.set_ylabel("Обводнённость, %", color=C("WC"))
    ax_w.tick_params(axis="y", colors=C("WC"))
    ax_w.set_ylim(0, 100)
    ax_w.grid(False)
    lines = l1 + l2 + l3 + l5 + l4
    ax.legend(lines, [ln.get_label() for ln in lines], loc="upper center", bbox_to_anchor=(0.5, -0.12),
              ncol=len(lines), fontsize=8, frameon=False)
    ax.set_title("График работы скважины")
    fig.autofmt_xdate()
    return fig


def survey_chart(survey, ports=(), funnel_md: float = 0.0, w=8.0, h=7.5) -> Figure:
    """Геометрия ствола: вертикальный профиль, план, горизонтальный участок с муфтами."""
    fig = _fig(w, h)
    t = survey_trajectory(survey)
    if len(t.md) < 2:
        ax = fig.add_subplot()
        ax.axis("off")
        ax.text(0.5, 0.5, "Нет данных инклинометрии\n(нужно минимум 2 замера: MD, зенит, азимут)",
                ha="center", va="center", transform=ax.transAxes, color=GREY)
        return fig
    gs = fig.add_gridspec(2, 2, width_ratios=[1.6, 1], height_ratios=[1.25, 1])
    ax_vs = fig.add_subplot(gs[0, 0])
    ax_pl = fig.add_subplot(gs[0, 1])
    ax_hz = fig.add_subplot(gs[1, :])
    az, vs = t.vertical_section()
    ports = [p for p in ports if t.md[0] <= p.md <= t.md[-1] + 1e-6]

    def at(md, ys):
        return interp(md, t.md, ys)

    # вертикальный профиль
    ax_vs.plot(vs, t.tvd, color=C("WELL"), lw=1.6, label="Ствол")
    ax_vs.invert_yaxis()
    ax_vs.set_xlabel(f"Смещение по азимуту {az:.0f}°, м")
    ax_vs.set_ylabel("TVD, м")
    ax_vs.set_title("Вертикальный профиль")
    # план
    ax_pl.plot(t.east, t.north, color=C("WELL"), lw=1.6, label="Ствол")
    ax_pl.plot([0], [0], "o", color=GREY, ms=5, label="Устье")
    ax_pl.set_aspect("equal", adjustable="datalim")
    ax_pl.set_xlabel("Восток, м")
    ax_pl.set_ylabel("Север, м")
    ax_pl.set_title("План")
    # горизонтальный участок
    start = min([p.md for p in ports] + [t.md[-1]]) - 250 if ports else t.md[-1] - 1200
    i0 = max(0, next((i for i, m in enumerate(t.md) if m >= start), 0) - 1)
    ax_hz.plot(t.md[i0:], t.tvd[i0:], color=C("WELL"), lw=1.6, label="Ствол")
    ax_hz.invert_yaxis()
    ax_hz.set_xlabel("MD, м")
    ax_hz.set_ylabel("TVD, м")
    ax_hz.set_title("Горизонтальный участок (масштаб по TVD увеличен)")
    for p in ports:
        col = C("PORT") if p.treat else C("PORT_OFF")
        x_vs, y = at(p.md, vs), at(p.md, t.tvd)
        ax_vs.plot(x_vs, y, "v", color=col, ms=6, label=f"МГРП{p.number}")
        ax_pl.plot(at(p.md, t.east), at(p.md, t.north), "v", color=col, ms=6, label=f"МГРП{p.number}")
        ax_hz.plot(p.md, y, "v", color=col, ms=8, label=f"МГРП{p.number}")
        ax_hz.annotate(f"МГРП{p.number}\n{p.md:.0f}", (p.md, y), textcoords="offset points",
                       xytext=(0, 9), ha="center", fontsize=7, color=col)
    if funnel_md and t.md[0] <= funnel_md <= t.md[-1]:
        y = at(funnel_md, t.tvd)
        ax_hz.axvline(funnel_md, color=C("FUNNEL"), ls="--", lw=1)
        ax_hz.annotate(f"Воронка {funnel_md:.0f}", (funnel_md, y), textcoords="offset points",
                       xytext=(4, -14), fontsize=7, color=C("FUNNEL"))
        ax_vs.plot(at(funnel_md, vs), y, "s", color=C("FUNNEL"), ms=5, label="Полированная воронка")
    lo, hi = ax_hz.get_ylim()
    pad = max(2.0, abs(lo - hi) * 0.25)
    ax_hz.set_ylim(lo + pad, hi - pad)
    handles = [Patch(color=C("PORT"), label="Муфта ГРП (обрабатывается)"),
               Patch(color=C("PORT_OFF"), label="Муфта ГРП (не обрабатывается)")]
    if funnel_md:
        handles.append(Patch(color=C("FUNNEL"), label="Полированная воронка"))
    ax_hz.legend(handles=handles, loc="lower left", fontsize=7, ncol=3)
    fig.suptitle(f"Геометрия ствола: забой MD {t.md[-1]:.0f} м, TVD {t.tvd[-1]:.1f} м, "
                 f"смещение {vs[-1]:.0f} м", fontsize=10)
    return fig


def all_charts(res: CalcResult, frac_pressure: float):
    tr = treated(res.ports)
    out = [
        ("fracture_detail", "Прохождение ГКС по трещинам ГРП (разлиновка расстояния)", fracture_detail(res)),
        ("fracture_plan", "Схема трещин и зоны промывки (вид в плане)", fracture_plan(res)),
        ("history", "Диаграмма работы скважины с потерей продуктивности (входной контроль)",
         history_chart(res)),
        ("forecast", "Планируемые параметры работы скважины на 1 год", forecast_chart(res)),
    ]
    if tr:
        out.append(("pump_stage1", "Режим закачки на 1 стадию", pumping_chart(res, frac_pressure, 1)))
    out += [
        ("pump_all", "Режимы технологических закачек на все стадии", pumping_chart(res, frac_pressure)),
        ("skin", "Изменение скин-фактора", skin_chart(res)),
    ]
    return out
