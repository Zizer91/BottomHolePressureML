"""Пути к ресурсам, работающие и из исходников, и из exe (PyInstaller)."""
import os
import sys


def asset(name: str) -> str:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, "acidclean", "assets", name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", name)
