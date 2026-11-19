# -*- mode: python ; coding: utf-8 -*-
# Сборка: pyinstaller --noconfirm --clean AcidCleanPRO.spec
a = Analysis(
    ['main.py'],
    pathex=[],
    datas=[('acidclean/assets', 'acidclean/assets')],
    hiddenimports=[],
    excludes=['tkinter', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.Qt3DCore',
              'PySide6.QtQuick', 'PySide6.QtQml', 'PySide6.QtMultimedia', 'pandas', 'scipy', 'IPython'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='AcidCleanPRO',
    console=False,
    icon='acidclean/assets/icon.ico',
)
coll = COLLECT(exe, a.binaries, a.datas, name='AcidCleanPRO')
