"""Модель данных проекта AcidClean PRO.

Все величины хранятся в «промысловых» единицах, указанных в комментариях.
Проект целиком сохраняется в JSON (*.acp).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from datetime import date
from typing import List, Optional


@dataclass
class WellInfo:
    well: str = ""                 # № скважины
    pad: str = ""                  # куст
    field_name: str = ""           # месторождение
    formation: str = ""            # пласт
    customer: str = ""             # заказчик
    report_date: str = field(default_factory=lambda: date.today().strftime("%d.%m.%Y"))
    prepared_by: str = ""
    checked_by: str = ""


@dataclass
class Construction:
    casing_od: float = 178.0       # мм, ЭК
    casing_id: float = 159.6       # мм
    liner_od: float = 114.0        # мм, хвостовик
    liner_id: float = 99.2         # мм
    tubing_od: float = 60.3        # мм, НКТ для ОПЗ
    tubing_id: float = 50.3        # мм
    funnel_md: float = 0.0         # м, полированная воронка хвостовика
    rotor_altitude: float = 0.0    # м
    reservoir_tvd: float = 0.0     # м, TVD пласта от ротора (если нет инклинометрии)


@dataclass
class Port:
    """Муфта МГРП и параметры закреплённой трещины (из отчёта ГРП)."""
    number: int = 1
    md: float = 0.0                # м, глубина муфты по стволу
    xf: float = 0.0                # м, закреплённая полудлина
    height: float = 0.0            # м, закреплённая высота
    width_mm: float = 0.0          # мм, закреплённая ширина
    conductivity: float = 0.0      # мД·м
    permeability: float = 0.0      # мД, проницаемость трещины
    skin_frac: float = -6.2        # скин после ГРП (идеальный геометрический)
    treat: bool = True             # обрабатывать порт при ОПЗ
    acid_volume: Optional[float] = None    # м3, если None — берётся из дизайна
    flush_volume: Optional[float] = None   # м3, если None — берётся из дизайна


@dataclass
class Reservoir:
    p_res: float = 0.0             # атм, пластовое давление (текущее)
    p_res_initial: float = 0.0     # атм, начальное пластовое (для истории; 0 — как текущее)
    t_res: float = 0.0             # °C
    perm: float = 0.0              # мД, проницаемость пласта
    porosity: float = 0.18         # д.ед., пористость пласта
    oil_visc: float = 1.4          # сПз
    oil_density: float = 0.84      # г/см3 (поверхностная)
    water_density: float = 1.01    # г/см3
    drainage_radius: float = 250.0  # м, Rк для формулы Дюпюи
    well_radius: float = 0.076     # м, rc для формулы Дюпюи
    frac_pressure: float = 0.0     # атм, давление ГРП (разрыва) на забое


@dataclass
class Regime:
    """Режим работы до ОПЗ (входной контроль)."""
    q_liq: float = 0.0             # м3/сут
    q_oil: float = 0.0             # т/сут
    water_cut: float = 0.0         # %, весовая обводнённость
    p_bhp: float = 0.0             # атм
    skin_before: float = 0.5       # скин до ОПЗ (ГДИС или +0,5)
    skin_source: str = "принят по умолчанию (+0,5)"  # «ГДИС от ...» и т.п.


@dataclass
class HistoryRow:
    """Строка истории эксплуатации (МЭР / шахматка)."""
    date: str = ""                 # ДД.ММ.ГГГГ
    p_bhp: Optional[float] = None  # атм
    q_oil: Optional[float] = None  # т/сут
    q_liq: Optional[float] = None  # т/сут (как в МЭР)
    water_cut: Optional[float] = None  # % вес.
    p_res: Optional[float] = None  # атм, пластовое на дату (необязательно)


@dataclass
class SurveyRow:
    md: float = 0.0
    incl: float = 0.0              # зенит, °
    azim: float = 0.0              # азимут, °


@dataclass
class Design:
    acid_name: str = "ГКС (2%HF+14%HCl)"
    acid_density: float = 1.07     # г/см3
    acid_visc: float = 1.0         # сПз
    flush_name: str = "Техническая жидкость"
    flush_density: float = 1.02    # г/см3
    acid_mode: str = "fixed"       # "fixed" — объём на порт задан, "pore" — доля порового объёма трещины
    acid_volume: float = 12.0      # м3 на порт (режим "fixed")
    pore_fraction: float = 0.5     # доля порового объёма трещины (режим "pore")
    flush_volume: float = 10.0     # м3 на порт
    rate: float = 0.5              # м3/мин
    pack_porosity: float = 0.30    # пористость пропантной пачки
    skin_after_mode: str = "fixed"  # "fixed" — задан, "calc" — по доле промытой трещины
    skin_after: float = -2.0       # скин после ОПЗ при режиме "fixed"
    injectivity: float = 4.3       # м3/сут/атм, приемистость порта до ОПЗ (уточнить тестом)
    friction_factor: float = 1.0   # множитель потерь на трение (понизитель трения < 1)
    gap_minutes: float = 0.0       # мин, пауза между портами на графике
    forecast_decline: float = 0.0  # %/мес, темп падения эффекта; 0 — оценить по истории
    forecast_months: int = 12


@dataclass
class Project:
    well: WellInfo = field(default_factory=WellInfo)
    construction: Construction = field(default_factory=Construction)
    reservoir: Reservoir = field(default_factory=Reservoir)
    regime: Regime = field(default_factory=Regime)
    design: Design = field(default_factory=Design)
    ports: List[Port] = field(default_factory=list)
    history: List[HistoryRow] = field(default_factory=list)
    survey: List[SurveyRow] = field(default_factory=list)
    notes: str = ""

    # ---- сериализация -------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        def build(dc, data):
            if data is None:
                return dc()
            names = {f.name for f in fields(dc)}
            return dc(**{k: v for k, v in data.items() if k in names})

        return cls(
            well=build(WellInfo, d.get("well")),
            construction=build(Construction, d.get("construction")),
            reservoir=build(Reservoir, d.get("reservoir")),
            regime=build(Regime, d.get("regime")),
            design=build(Design, d.get("design")),
            ports=[build(Port, p) for p in d.get("ports", [])],
            history=[build(HistoryRow, h) for h in d.get("history", [])],
            survey=[build(SurveyRow, s) for s in d.get("survey", [])],
            notes=d.get("notes", ""),
        )

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> "Project":
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))
