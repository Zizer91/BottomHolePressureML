"""Графический интерфейс AcidClean PRO (PySide6)."""
from __future__ import annotations

import os
import sys
import traceback

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QFileDialog, QFormLayout,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
                               QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSplitter,
                               QTableWidget, QTableWidgetItem, QTabWidget, QTextBrowser, QVBoxLayout,
                               QWidget)

from . import calc, charts, io_excel, report_pdf, report_xlsx
from . import report_text as rt
from .models import HistoryRow, Port, Project, SurveyRow
from .resources import asset

FILE_FILTER = "Проект AcidClean PRO (*.acp);;Все файлы (*)"
XLSX_FILTER = "Excel (*.xlsx *.xlsm);;Все файлы (*)"

CHOICES = {
    ("design", "acid_mode"): [("fixed", "Объём на порт задан"), ("pore", "Доля порового объёма трещины")],
    ("design", "skin_after_mode"): [("fixed", "Задан (по умолчанию −2)"),
                                    ("calc", "Расчёт по доле промытой трещины")],
}

SECTIONS = [
    ("Скважина и конструкция", [("well", "Скважина"), ("construction", "Конструкция и оборудование")]),
    ("Пласт и режим до ОПЗ", [("reservoir", "Пласт"), ("regime", "Режим работы до ОПЗ (входной контроль)")]),
    ("Дизайн ОПЗ", [("design", "Реагенты, объёмы, режим закачки, прогноз")]),
]


def _num(text: str):
    t = (text or "").strip().replace(",", ".").replace(" ", "")
    if t == "":
        return None
    return float(t)


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


class Table(QWidget):
    """Таблица с кнопками добавления/удаления строк."""

    def __init__(self, columns, parent=None, extra_buttons=()):
        super().__init__(parent)
        self.columns = columns  # [(заголовок, ключ, тип)] тип: float|int|str|bool|optfloat
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        add = QPushButton("Добавить строку")
        rem = QPushButton("Удалить выделенные")
        add.clicked.connect(lambda: self.table.insertRow(self.table.rowCount()))
        rem.clicked.connect(self._remove)
        bar.addWidget(add)
        bar.addWidget(rem)
        for b in extra_buttons:
            bar.addWidget(b)
        bar.addStretch()
        lay.addLayout(bar)
        self.table = QTableWidget(0, len(columns))
        self.table.setHorizontalHeaderLabels([c[0] for c in columns])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setDefaultSectionSize(110)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        lay.addWidget(self.table)

    def _remove(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)

    def set_rows(self, objs):
        self.table.setRowCount(0)
        for o in objs:
            r = self.table.rowCount()
            self.table.insertRow(r)
            for j, (_, key, typ) in enumerate(self.columns):
                v = getattr(o, key)
                if typ == "bool":
                    it = QTableWidgetItem()
                    it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    it.setCheckState(Qt.CheckState.Checked if v else Qt.CheckState.Unchecked)
                else:
                    it = QTableWidgetItem(_fmt(v))
                self.table.setItem(r, j, it)

    def rows(self, factory):
        out = []
        for r in range(self.table.rowCount()):
            vals = {}
            empty = True
            for j, (title, key, typ) in enumerate(self.columns):
                it = self.table.item(r, j)
                if typ == "bool":
                    vals[key] = it is None or it.checkState() == Qt.CheckState.Checked
                    continue
                text = it.text() if it else ""
                if text.strip():
                    empty = False
                try:
                    if typ == "str":
                        vals[key] = text.strip()
                    elif typ == "int":
                        vals[key] = int(_num(text) or 0)
                    elif typ == "optfloat":
                        vals[key] = _num(text)
                    else:
                        vals[key] = _num(text) or 0.0
                except ValueError:
                    raise ValueError(f"Строка {r + 1}, «{title}»: «{text}» не число")
            if not empty:
                out.append(factory(**vals))
        return out


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project = Project()
        self.path = None
        self.result = None
        self.fields = {}
        self.setWindowTitle(rt.APP_NAME)
        self.resize(1280, 860)
        try:
            self.setWindowIcon(QIcon(asset("logo.png")))
        except Exception:
            pass
        self._build_actions()
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        for title, secs in SECTIONS:
            self.tabs.addTab(self._form_tab(secs), title)
        self.ports = Table([("№ муфты", "number", "int"), ("MD, м", "md", "float"), ("Xf, м", "xf", "float"),
                            ("H, м", "height", "float"), ("w, мм", "width_mm", "float"),
                            ("Проводимость,\nмД·м", "conductivity", "float"),
                            ("Проницаемость,\nмД", "permeability", "float"),
                            ("Скин\nпосле ГРП", "skin_frac", "float"), ("Обрабатывать", "treat", "bool"),
                            ("ГКС, м3\n(свой)", "acid_volume", "optfloat"),
                            ("Продавка, м3\n(своя)", "flush_volume", "optfloat")])
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("Муфты МГРП и параметры закреплённых трещин из отчётов ГРП (столбец «факт»). "
                             "Закачка ведётся от забоя к устью. Пустые «ГКС/Продавка» — берутся из дизайна."))
        lay.addWidget(self.ports)
        self.tabs.addTab(w, "Муфты и трещины ГРП")
        b_hist = QPushButton("Импорт из Excel (МЭР)…")
        b_hist.clicked.connect(self.import_history)
        self.history = Table([("Дата", "date", "str"), ("Рзаб, атм", "p_bhp", "optfloat"),
                              ("Qн, т/сут", "q_oil", "optfloat"), ("Qж, т/сут", "q_liq", "optfloat"),
                              ("Обв., % вес.", "water_cut", "optfloat"), ("Рпл, атм\n(необяз.)", "p_res", "optfloat")],
                             extra_buttons=[b_hist])
        self.tabs.addTab(self.history, "История (входной контроль)")
        b_surv = QPushButton("Импорт из Excel…")
        b_surv.clicked.connect(self.import_survey)
        self.survey = Table([("MD, м", "md", "float"), ("Зенит, °", "incl", "float"),
                             ("Азимут, °", "azim", "float")], extra_buttons=[b_surv])
        self.tabs.addTab(self._survey_tab(), "Инклинометрия")
        self.notes = QPlainTextEdit()
        nw = QWidget()
        nl = QVBoxLayout(nw)
        nl.addWidget(QLabel("Примечание (выводится во введении отчёта):"))
        nl.addWidget(self.notes)
        self.tabs.addTab(nw, "Примечание")
        self.tabs.addTab(self._results_tab(), "Результаты")
        self.populate()
        self.statusBar().showMessage("Создайте новый проект, откройте *.acp или загрузите шаблон Excel")

    # ------------------------------------------------------------------ UI
    def _build_actions(self):
        tb = self.addToolBar("Главная")
        tb.setMovable(False)
        menu = self.menuBar().addMenu("Файл")

        def act(text, slot, key=None, toolbar=True):
            a = QAction(text, self)
            a.triggered.connect(slot)
            if key:
                a.setShortcut(QKeySequence(key))
            menu.addAction(a)
            if toolbar:
                tb.addAction(a)
            return a

        act("Новый", self.new_project, "Ctrl+N")
        act("Открыть…", self.open_project, "Ctrl+O")
        act("Сохранить", self.save_project, "Ctrl+S")
        act("Сохранить как…", self.save_project_as, None, False)
        menu.addSeparator()
        tb.addSeparator()
        act("Загрузить шаблон Excel…", self.import_template)
        act("Создать шаблон Excel…", self.export_template, None, False)
        menu.addSeparator()
        tb.addSeparator()
        act("Рассчитать", self.run_calc, "F5")
        act("Отчёт PDF…", lambda: self.export_report("pdf"))
        act("Отчёт XLSX…", lambda: self.export_report("xlsx"))
        menu.addSeparator()
        act("Выход", self.close, "Ctrl+Q", False)
        hm = self.menuBar().addMenu("Справка")
        a = QAction("О программе", self)
        a.triggered.connect(self.about)
        hm.addAction(a)

    def _form_tab(self, secs):
        w = QWidget()
        lay = QVBoxLayout(w)
        for sec, title in secs:
            box = QGroupBox(title)
            form = QFormLayout(box)
            for s, attr, label, unit in io_excel.FIELDS:
                if s != sec:
                    continue
                if (s, attr) in CHOICES:
                    ed = QComboBox()
                    for val, text in CHOICES[(s, attr)]:
                        ed.addItem(text, val)
                else:
                    ed = QLineEdit()
                if (s, attr) in CHOICES:
                    label = label.split(" (")[0]
                form.addRow(f"{label}{', ' + unit if unit else ''}:", ed)
                self.fields[(s, attr)] = ed
            lay.addWidget(box)
        lay.addStretch()
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(w)
        return sc

    def _survey_tab(self):
        sp = QSplitter()
        self.survey.table.horizontalHeader().setDefaultSectionSize(90)
        sp.addWidget(self.survey)
        right = QWidget()
        self.survey_chart_layout = QVBoxLayout(right)
        self.survey_chart_layout.setContentsMargins(0, 0, 0, 0)
        sp.addWidget(right)
        sp.setSizes([360, 900])
        self.survey_canvas = None
        self.survey_toolbar = None
        self._survey_timer = QTimer(self)
        self._survey_timer.setSingleShot(True)
        self._survey_timer.setInterval(500)
        self._survey_timer.timeout.connect(self.refresh_survey_chart)
        for t in (self.survey.table, self.ports.table):
            t.itemChanged.connect(lambda *_: self._survey_timer.start())
            t.model().rowsRemoved.connect(lambda *_: self._survey_timer.start())
        return sp

    def refresh_survey_chart(self):
        """Перерисовать геометрию ствола по текущей таблице (ошибочные ячейки не мешают)."""
        try:
            rows = self.survey.rows(SurveyRow)
        except ValueError as e:
            self.statusBar().showMessage(f"Инклинометрия: {e}")
            return
        try:
            ports = self.ports.rows(Port)
        except ValueError:
            ports = []
        try:
            funnel = _num(self.fields[("construction", "funnel_md")].text()) or 0.0
        except ValueError:
            funnel = 0.0
        fig = charts.survey_chart(rows, ports, funnel)
        for wdg in (self.survey_toolbar, self.survey_canvas):
            if wdg is not None:
                self.survey_chart_layout.removeWidget(wdg)
                wdg.setParent(None)
        self.survey_canvas = FigureCanvasQTAgg(fig)
        self.survey_toolbar = NavigationToolbar2QT(self.survey_canvas, self)
        self.survey_chart_layout.addWidget(self.survey_toolbar)
        self.survey_chart_layout.addWidget(self.survey_canvas, 1)

    def _results_tab(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        sp = QSplitter()
        self.summary = QTextBrowser()
        sp.addWidget(self.summary)
        right = QWidget()
        rl = QVBoxLayout(right)
        self.chart_box = QComboBox()
        self.chart_box.currentIndexChanged.connect(self.show_chart)
        rl.addWidget(self.chart_box)
        self.canvas_holder = QVBoxLayout()
        rl.addLayout(self.canvas_holder, 1)
        sp.addWidget(right)
        sp.setSizes([480, 800])
        lay.addWidget(sp)
        self._charts = []
        self.canvas = None
        return w

    # ------------------------------------------------------------ binding
    def populate(self):
        p = self.project
        for (s, attr), ed in self.fields.items():
            v = getattr(getattr(p, s), attr)
            if isinstance(ed, QComboBox):
                i = ed.findData(v)
                ed.setCurrentIndex(max(0, i))
            else:
                ed.setText(_fmt(v))
        self.ports.set_rows(p.ports)
        self.history.set_rows(p.history)
        self.survey.set_rows(p.survey)
        self.notes.setPlainText(p.notes)
        self.refresh_survey_chart()
        self._update_title()

    def collect(self) -> Project:
        p = self.project
        errs = []
        for (s, attr), ed in self.fields.items():
            obj = getattr(p, s)
            cur = getattr(obj, attr)
            if isinstance(ed, QComboBox):
                setattr(obj, attr, ed.currentData())
                continue
            text = ed.text()
            try:
                if isinstance(cur, bool):
                    setattr(obj, attr, text.strip().lower() in ("да", "1", "true"))
                elif isinstance(cur, int):
                    setattr(obj, attr, int(_num(text) or 0))
                elif isinstance(cur, float):
                    setattr(obj, attr, _num(text) or 0.0)
                else:
                    setattr(obj, attr, text.strip())
            except ValueError:
                errs.append(f"«{text}» — не число ({attr})")
        if errs:
            raise ValueError("\n".join(errs))
        p.ports = self.ports.rows(Port)
        p.history = self.history.rows(HistoryRow)
        p.survey = self.survey.rows(SurveyRow)
        p.notes = self.notes.toPlainText()
        return p

    def _update_title(self):
        name = os.path.basename(self.path) if self.path else "новый проект"
        self.setWindowTitle(f"{rt.APP_NAME} — {name}")

    # ------------------------------------------------------------ actions
    def _guard(self, fn):
        try:
            return fn()
        except Exception as e:  # показываем пользователю, а не падаем
            QMessageBox.critical(self, rt.APP_NAME, str(e) or traceback.format_exc())
            return None

    def new_project(self):
        self.project, self.path, self.result = Project(), None, None
        self.populate()
        self.summary.clear()

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Открыть проект", "", FILE_FILTER)
        if path:
            self.load_path(path)

    def load_path(self, path):
        def go():
            self.project = Project.load(path)
            self.path = path
            self.populate()
            self.statusBar().showMessage(f"Открыт {path}")
        self._guard(go)

    def save_project(self):
        if not self.path:
            return self.save_project_as()

        def go():
            self.collect().save(self.path)
            self.statusBar().showMessage(f"Сохранено: {self.path}")
        self._guard(go)

    def save_project_as(self):
        w = self.project.well
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить проект", f"{w.well or 'проект'}.acp",
                                              FILE_FILTER)
        if path:
            if not path.lower().endswith(".acp"):
                path += ".acp"
            self.path = path
            self._update_title()
            self.save_project()

    def import_template(self):
        path, _ = QFileDialog.getOpenFileName(self, "Загрузить шаблон Excel", "", XLSX_FILTER)
        if not path:
            return

        def go():
            self.collect()
            self.project = io_excel.import_template(path, self.project)
            self.populate()
            self.statusBar().showMessage(f"Загружено из {path}")
        self._guard(go)

    def export_template(self):
        path, _ = QFileDialog.getSaveFileName(self, "Создать шаблон Excel", "шаблон_AcidClean.xlsx",
                                              XLSX_FILTER)
        if path:
            self._guard(lambda: (self.collect(), io_excel.export_template(self.project, path),
                                 self.statusBar().showMessage(f"Шаблон сохранён: {path}")))

    def import_history(self):
        path, _ = QFileDialog.getOpenFileName(self, "История эксплуатации (МЭР)", "", XLSX_FILTER)
        if not path:
            return

        def go():
            rows = io_excel.import_history(path)
            if not rows:
                raise ValueError("Не найден лист с заголовками «Дата», «Рзаб/забойное», «нефть», "
                                 "«жидкость», «обводнённость»")
            self.history.set_rows(rows)
            self.statusBar().showMessage(f"Загружено строк истории: {len(rows)}")
        self._guard(go)

    def import_survey(self):
        path, _ = QFileDialog.getOpenFileName(self, "Инклинометрия", "", XLSX_FILTER)
        if not path:
            return

        def go():
            rows = io_excel.import_survey(path)
            if not rows:
                raise ValueError("Не найден лист с заголовками «Глубина», «Зенит», «Азимут»")
            self.survey.set_rows(rows)
            self.refresh_survey_chart()
            self.statusBar().showMessage(f"Загружено замеров инклинометрии: {len(rows)}")
        self._guard(go)

    def run_calc(self):
        def go():
            p = self.collect()
            self.result = calc.run(p)
            self.show_results()
            self.tabs.setCurrentIndex(self.tabs.count() - 1)
            self.statusBar().showMessage("Расчёт выполнен")
            return True
        return self._guard(go)

    def export_report(self, kind):
        if not self.run_calc():
            return
        w = self.project.well
        default = f"ОПЗ_{w.well}_{w.pad}.{kind}".replace(" ", "_")
        flt = "PDF (*.pdf)" if kind == "pdf" else "Excel (*.xlsx)"
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить отчёт", default, flt)
        if not path:
            return
        if not path.lower().endswith("." + kind):
            path += "." + kind

        def go():
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                if kind == "pdf":
                    report_pdf.build_pdf(self.project, self.result, path)
                else:
                    report_xlsx.build_xlsx(self.project, self.result, path)
            finally:
                QApplication.restoreOverrideCursor()
            self.statusBar().showMessage(f"Отчёт сохранён: {path}")
            if QMessageBox.question(self, rt.APP_NAME, f"Отчёт сохранён:\n{path}\n\nОткрыть?") == \
                    QMessageBox.StandardButton.Yes:
                if sys.platform.startswith("win"):
                    os.startfile(path)  # noqa: S606
        self._guard(go)

    # ------------------------------------------------------------ results
    def show_results(self):
        p, r = self.project, self.result

        def table(head, rows):
            h = "".join(f"<th>{x}</th>" for x in head)
            b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
            return (f"<table border=1 cellspacing=0 cellpadding=3 style='border-collapse:collapse'>"
                    f"<tr style='background:#F3E6E8'>{h}</tr>{b}</table>")

        html = [f"<h2 style='color:#9B1B30'>Результаты: скв. {p.well.well} куст {p.well.pad}</h2>"]
        if r.warnings:
            html.append("<p style='color:#B00020'><b>Предупреждения:</b><br>" +
                        "<br>".join(r.warnings) + "</p>")
        head, rows = rt.table_results(r)
        html += ["<h3>Результаты обработки</h3>", table(head, rows)]
        head, rows = rt.table_fractures(p, r)
        html += ["<h3>Трещины и объёмы ГКС</h3>", table(head, rows)]
        head, rows = rt.table_plan(p, r)
        html += ["<h3>План закачки</h3>", table(head, rows)]
        head, rows = rt.table_pumping(r)
        html += ["<h3>Давления закачки</h3>", table(head, rows)]
        html += ["<h3>Заключение</h3><ul>"] + [f"<li>{t}</li>" for t in rt.conclusions(p, r)] + ["</ul>"]
        self.summary.setHtml("".join(html))
        self._charts = charts.all_charts(r, p.reservoir.frac_pressure)
        self.chart_box.blockSignals(True)
        self.chart_box.clear()
        for _, title, _ in self._charts:
            self.chart_box.addItem(title)
        self.chart_box.blockSignals(False)
        self.show_chart(0)

    def show_chart(self, i):
        if not self._charts or i < 0:
            return
        if self.canvas is not None:
            self.canvas_holder.removeWidget(self.canvas)
            self.canvas.setParent(None)
        self.canvas = FigureCanvasQTAgg(self._charts[i][2])
        self.canvas_holder.addWidget(self.canvas)

    def about(self):
        box = QMessageBox(self)
        box.setWindowTitle(rt.APP_NAME)
        try:
            box.setIconPixmap(QPixmap(asset("logo.png")).scaledToWidth(160))
        except Exception:
            pass
        box.setText(f"<b>{rt.APP_NAME}</b><br>Расчёт дизайна многостадийной ОПЗ (МОПЗ) "
                    "по трещинам ГРП.<br><br>Методика: объём и поровый объём закреплённой трещины, "
                    "глубина проникновения ГКС, скин-фактор, формула Дюпюи, прогноз на 1 год.")
        box.exec()


def main(argv=None):
    app = QApplication(argv or sys.argv)
    app.setApplicationName(rt.APP_NAME)
    win = MainWindow()
    args = (argv or sys.argv)[1:]
    if args and os.path.exists(args[0]):
        win.load_path(args[0])
    win.show()
    return app.exec()
