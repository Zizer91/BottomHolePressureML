"""Сверка расчётного ядра с отчётом-примером FracSimPRO (демо-проект examples/demo.acp)."""
import math
import os
import sys

import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))

from acidclean import calc  # noqa: E402
from acidclean.models import Project  # noqa: E402

EXAMPLE = os.path.join(HERE, "..", "examples", "demo.acp")

# Таблица 1.3 отчёта-примера: порт -> (Vтр, Vпор, Lпрон при 12 м3)
REPORT = {
    2: (78.89, 23.67, 116), 3: (79.23, 23.77, 111), 4: (75.49, 22.65, 112),
    5: (72.70, 21.81, 116), 6: (79.23, 23.77, 111), 7: (74.97, 22.49, 117),
}


@pytest.fixture
def project():
    return Project.load(EXAMPLE)


def test_fracture_volumes_match_report(project):
    res = {r.port.number: r for r in calc.fracture_results(project)}
    for n, (v, vp, pen) in REPORT.items():
        assert res[n].frac_volume == pytest.approx(v, abs=0.02)
        assert res[n].pore_volume == pytest.approx(vp, abs=0.01)
        assert int(res[n].penetration) == pen


def test_total_height_and_volumes(project):
    r = calc.run(project)
    assert r.total_height == pytest.approx(404.5)
    assert r.total_acid == pytest.approx(72.0)
    assert r.total_minutes == pytest.approx(6 * 44)


def test_order_of_ports_bottom_up(project):
    plan = calc.injection_plan(project)
    assert [p.port_number for p in plan if p.kind == "Кислота"] == [2, 3, 4, 5, 6, 7]


def test_kprod_before_matches_report(project):
    prod = calc.productivity(project)
    assert prod.j_before == pytest.approx(0.112, abs=0.0005)


def test_calc_skin_mode_close_to_report(project):
    project.design.skin_after_mode = "calc"
    prod = calc.productivity(project)
    # отчёт FracSimPRO: -3.1; линейная модель доли промытой трещины даёт -3.0
    assert prod.skin_after == pytest.approx(-3.0, abs=0.05)


def test_dupuit_ratio(project):
    project.design.skin_after_mode = "fixed"
    project.design.skin_after = -2.0
    prod = calc.productivity(project)
    lt = math.log(250 / 0.076)
    assert prod.j_after / prod.j_before == pytest.approx((lt + 0.5) / (lt - 2.0))
    # обводнённость и забойное не меняются, нефть пропорциональна жидкости
    assert prod.q_oil_after / prod.q_liq_after == pytest.approx(11.6 / 19)


def test_dupuit_reproduces_report_with_its_ln_term(project):
    # при ln(Rк/rc)=6.663 и S=-3.1 формула Дюпюи даёт Qж=38.2 как в отчёте
    project.design.skin_after = -3.1
    project.reservoir.well_radius = 0.1
    project.reservoir.drainage_radius = 0.1 * math.exp(6.663)
    prod = calc.productivity(project)
    assert prod.q_liq_after == pytest.approx(38.2, abs=0.05)


def test_pumping_pressures(project):
    sim = calc.simulate_pumping(project)
    first = [p for p in sim.points if p.stage == 1]
    assert first[0].p_bh == pytest.approx(204 + 720 / 4.3, abs=1)
    # скин в конце закачки ГКС на порту равен скину после ОПЗ
    assert first[-1].skin == pytest.approx(-2.0)
    # вся кислота ушла в пласт (продавка больше объёма НКТ)
    assert first[-1].acid_in == pytest.approx(12.0)
    assert sim.tubing_volumes[0] == pytest.approx(math.pi * 0.0503 ** 2 / 4 * 3903.96)


def test_forecast(project):
    r = calc.run(project)
    assert len(r.forecast.rows) == 12
    assert r.forecast.rows[0].q_liq == pytest.approx(r.prod.q_liq_after)
    assert r.forecast.extra_oil_total > 0


def test_save_load_roundtrip(project, tmp_path):
    path = tmp_path / "p.acp"
    project.save(str(path))
    p2 = Project.load(str(path))
    assert p2.to_dict() == project.to_dict()


def test_validation():
    with pytest.raises(ValueError):
        calc.run(Project())


def test_forecast_table_mode(project):
    from acidclean.models import ForecastPoint
    r_exp = calc.run(project)
    dec = r_exp.forecast.decline
    # таблица по экспоненте даёт те же дебиты, что и режим exp
    project.design.forecast_mode = "table"
    project.forecast_table = calc.exp_table(dec, 12)
    r_tab = calc.run(project)
    assert r_tab.forecast.mode == "table"
    for a, b in zip(r_exp.forecast.rows, r_tab.forecast.rows):
        assert b.q_liq == pytest.approx(a.q_liq, rel=2e-3)
        assert b.q_oil == pytest.approx(a.q_oil, rel=2e-3)
    # рост обводнённости снижает нефть, снижение Рзаб увеличивает жидкость пропорционально депрессии
    q1 = r_tab.prod.q_liq_after
    project.forecast_table = [ForecastPoint(1, 100, None, None), ForecastPoint(2, 100, 50.0, 34 - 17)]
    r = calc.run(project)
    m1, m2 = r.forecast.rows
    assert m1.q_liq == pytest.approx(q1)
    assert m1.q_oil == pytest.approx(r.prod.q_oil_after)
    assert m2.q_liq == pytest.approx(q1 * (204 - 17) / (204 - 34))
    assert m2.q_oil / m2.q_liq < m1.q_oil / m1.q_liq
    assert m2.water_cut == 50.0 and m2.p_bhp == 17


def test_forecast_table_validation(project):
    project.design.forecast_mode = "table"
    project.forecast_table = []
    with pytest.raises(ValueError, match="таблица прогноза пуста"):
        calc.run(project)


def test_forecast_negative_effect_not_counted(project):
    from acidclean.models import ForecastPoint
    project.design.forecast_mode = "table"
    project.forecast_table = [ForecastPoint(1, 100), ForecastPoint(2, 10)]
    fc = calc.run(project).forecast
    assert fc.rows[1].extra_oil == 0
    assert fc.effect_end_month == 2
