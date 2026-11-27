"""Интерактивность графиков matplotlib в интерфейсе.

* Наведение курсора на точку линии или столбец показывает подсказку со значением.
* Клик по элементу легенды скрывает / показывает соответствующую линию.
Масштаб и перемещение — стандартная панель NavigationToolbar.
"""
from __future__ import annotations

from datetime import date, datetime

import numpy as np
from matplotlib.container import BarContainer
from matplotlib.dates import num2date
from matplotlib.lines import Line2D
from matplotlib.transforms import IdentityTransform

HOVER_PX = 9


def _fmt(v):
    if isinstance(v, (datetime, date)):
        return v.strftime("%d.%m.%Y")
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    if v != v:
        return "—"
    a = abs(v)
    if a >= 1000:
        return f"{v:.0f}"
    if a >= 10:
        return f"{v:.1f}"
    return f"{v:.3g}" if a < 1 else f"{v:.2f}"


def _axis_name(label: str, default: str) -> str:
    return label.split("\n")[0] if label else default


def _is_date_axis(ax) -> bool:
    try:
        return "date" in type(ax.xaxis.get_converter()).__module__
    except Exception:
        return False


class Interactive:
    def __init__(self, fig, canvas):
        self.fig = fig
        self.canvas = canvas
        self.legend_map = {}
        self.annot = fig.text(0, 0, "", transform=IdentityTransform(), fontsize=8, zorder=1000,
                              va="bottom", ha="left", visible=False,
                              bbox=dict(boxstyle="round,pad=0.4", fc="#FFFFF0", ec="#888888", alpha=0.95))
        self._setup_legends()
        canvas.mpl_connect("motion_notify_event", self.on_move)
        canvas.mpl_connect("pick_event", self.on_pick)
        canvas.mpl_connect("figure_leave_event", lambda e: self._hide())

    # ------------------------------------------------------------ legend
    def _artists_by_label(self, label):
        out = []
        for ax in self.fig.axes:
            for a in list(ax.lines) + list(ax.collections) + list(ax.patches):
                if a.get_label() == label:
                    out.append(a)
            for cont in ax.containers:
                if cont.get_label() == label:
                    out.extend(cont.patches if isinstance(cont, BarContainer) else [])
        return out

    def _setup_legends(self):
        for ax in self.fig.axes:
            leg = ax.get_legend()
            if leg is None:
                continue
            handles = getattr(leg, "legend_handles", None) or getattr(leg, "legendHandles", [])
            for h, t in zip(handles, leg.get_texts()):
                targets = self._artists_by_label(t.get_text())
                if not targets:
                    continue
                for a in (h, t):
                    a.set_picker(6)
                    self.legend_map[a] = (targets, h, t)

    def on_pick(self, event):
        item = self.legend_map.get(event.artist)
        if not item:
            return
        targets, h, t = item
        vis = not targets[0].get_visible()
        for a in targets:
            a.set_visible(vis)
        h.set_alpha(1.0 if vis else 0.25)
        t.set_alpha(1.0 if vis else 0.4)
        self.canvas.draw_idle()

    # ------------------------------------------------------------ hover
    def _hide(self):
        if self.annot.get_visible():
            self.annot.set_visible(False)
            self.canvas.draw_idle()

    def _nearest_line(self, event):
        best = None
        for ax in self.fig.axes:
            for ln in ax.lines:
                if not isinstance(ln, Line2D) or not ln.get_visible():
                    continue
                label = ln.get_label()
                if label.startswith("_"):
                    continue
                xy = np.asarray(ln.get_xydata(), dtype=float)
                if xy.size == 0:
                    continue
                pts = ln.get_transform().transform(xy)
                d = np.hypot(pts[:, 0] - event.x, pts[:, 1] - event.y)
                d[~np.isfinite(d)] = np.inf
                i = int(np.argmin(d))
                if d[i] <= HOVER_PX and (best is None or d[i] < best[0]):
                    best = (d[i], ln, i, pts[i])
        return best

    def _bar_under(self, event):
        for ax in reversed(self.fig.axes):
            for cont in reversed(ax.containers):       # верхний (последний нарисованный) столбец
                if not isinstance(cont, BarContainer):
                    continue
                for p in cont.patches:
                    if p.get_visible() and p.contains(event)[0]:
                        return ax, cont, p
        return None

    def on_move(self, event):
        if event.inaxes is None:
            return self._hide()
        hit = self._nearest_line(event)
        if hit:
            _, ln, i, (px, py) = hit
            ax = ln.axes
            xd, yd = ln.get_xdata(), ln.get_ydata()
            x = xd[i]
            if not isinstance(x, (datetime, date)) and _is_date_axis(ax):
                try:
                    x = num2date(float(x))
                except Exception:
                    pass
            same_x = len(set(np.round(np.asarray(ln.get_xydata(), dtype=float)[:, 0], 9))) == 1
            lines = [ln.get_label()]
            if not same_x:
                xname = _axis_name(ax.get_xlabel(), "Дата" if isinstance(x, (datetime, date)) else "x")
                lines.append(f"{xname}: {_fmt(x)}")
            lines.append(f"{_axis_name(ax.get_ylabel(), 'y')}: {_fmt(yd[i])}")
            self._show("\n".join(lines), px, py)
            return
        bar = self._bar_under(event)
        if bar:
            ax, cont, p = bar
            val = p.get_width() if cont.orientation == "horizontal" else p.get_height()
            name = cont.get_label() if not cont.get_label().startswith("_") else ""
            self._show(f"{name}: {_fmt(val)}" if name else _fmt(val), event.x, event.y)
            return
        self._hide()

    def _show(self, text, px, py):
        w, h = self.canvas.get_width_height()
        dpr = getattr(self.canvas, "device_pixel_ratio", 1) or 1
        w, h = w * dpr, h * dpr
        self.annot.set_text(text)
        self.annot.set_ha("right" if px > w * 0.7 else "left")
        self.annot.set_va("top" if py > h * 0.75 else "bottom")
        dx = -10 if px > w * 0.7 else 10
        dy = -10 if py > h * 0.75 else 10
        self.annot.set_position((px + dx, py + dy))
        self.annot.set_visible(True)
        self.canvas.draw_idle()


def attach(fig, canvas) -> Interactive:
    obj = Interactive(fig, canvas)
    canvas._acidclean_interactive = obj   # держим ссылку, иначе обработчики соберёт GC
    return obj
