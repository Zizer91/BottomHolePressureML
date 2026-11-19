@echo off
chcp 65001 >nul
rem Сборка AcidClean PRO в exe (Windows). Нужен Python 3.10+ (python.org).
cd /d %~dp0
python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m pytest tests -q || goto :error
pyinstaller --noconfirm --clean AcidCleanPRO.spec || goto :error
copy /Y examples\demo.acp dist\AcidCleanPRO\ >nul
echo.
echo Готово: dist\AcidCleanPRO\AcidCleanPRO.exe
echo Для передачи пользователю заархивируйте папку dist\AcidCleanPRO целиком.
goto :eof
:error
echo Ошибка сборки
exit /b 1
