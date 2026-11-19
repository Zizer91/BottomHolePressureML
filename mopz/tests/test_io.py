import os
import sys

import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))

from acidclean import calc, io_excel, report_pdf, report_xlsx  # noqa: E402
from acidclean.models import Project  # noqa: E402

EXAMPLE = os.path.join(HERE, "..", "examples", "demo.acp")


def test_template_roundtrip(tmp_path):
    p = Project.load(EXAMPLE)
    path = str(tmp_path / "t.xlsx")
    io_excel.export_template(p, path)
    p2 = io_excel.import_template(path)
    assert p2.well == p.well
    assert p2.reservoir == p.reservoir
    assert p2.design == p.design
    assert p2.ports == p.ports
    assert len(p2.history) == len(p.history)
    assert [s.md for s in p2.survey] == pytest.approx([s.md for s in p.survey])


def test_reports_build(tmp_path):
    p = Project.load(EXAMPLE)
    r = calc.run(p)
    pdf, xlsx = str(tmp_path / "r.pdf"), str(tmp_path / "r.xlsx")
    report_pdf.build_pdf(p, r, pdf)
    report_xlsx.build_xlsx(p, r, xlsx)
    assert os.path.getsize(pdf) > 50_000
    assert os.path.getsize(xlsx) > 20_000
