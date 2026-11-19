"""Точка входа AcidClean PRO.

    AcidCleanPRO                         — интерфейс
    AcidCleanPRO проект.acp              — интерфейс с открытым проектом
    AcidCleanPRO проект.acp --pdf r.pdf --xlsx r.xlsx
                                         — расчёт и отчёты без интерфейса
    AcidCleanPRO шаблон.xlsx --pdf r.pdf — то же из заполненного шаблона Excel
"""
import argparse
import sys


def batch(args) -> int:
    from acidclean import calc, io_excel, report_pdf, report_xlsx
    from acidclean.models import Project

    if args.project.lower().endswith((".xlsx", ".xlsm")):
        project = io_excel.import_template(args.project)
    else:
        project = Project.load(args.project)
    res = calc.run(project)
    if args.pdf:
        report_pdf.build_pdf(project, res, args.pdf)
    if args.xlsx:
        report_xlsx.build_xlsx(project, res, args.xlsx)
    for w in res.warnings:
        print("Внимание:", w)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="AcidCleanPRO")
    ap.add_argument("project", nargs="?", help="проект .acp или шаблон .xlsx")
    ap.add_argument("--pdf", help="сохранить PDF-отчёт без запуска интерфейса")
    ap.add_argument("--xlsx", help="сохранить XLSX-отчёт без запуска интерфейса")
    a, _ = ap.parse_known_args()
    if a.project and (a.pdf or a.xlsx):
        sys.exit(batch(a))
    from acidclean.gui import main
    sys.exit(main())
