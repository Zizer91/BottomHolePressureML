"""Пользовательские настройки программы (цвета графиков) — JSON в профиле пользователя."""
from __future__ import annotations

import json
import os
import sys


def settings_path() -> str:
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        folder = os.path.join(base, "AcidCleanPRO")
    else:
        folder = os.path.join(os.path.expanduser("~"), ".config", "acidclean")
    return os.path.join(folder, "settings.json")


def load() -> dict:
    try:
        with open(settings_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data: dict) -> None:
    path = settings_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def apply_palette() -> None:
    """Загрузить цвета из настроек и применить к графикам (интерфейс и отчёты)."""
    from . import charts
    charts.reset_palette()
    charts.set_palette(load().get("colors", {}))
