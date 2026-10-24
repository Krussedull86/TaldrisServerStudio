@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto missing
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -c "import PySide6; import winpty" >nul 2>nul
if errorlevel 1 .venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe app.py
if errorlevel 1 goto fail
exit /b 0
:missing
echo Installer Python 3.12 eller nyere fra python.org.
pause
exit /b 1
:fail
echo Oppstart feilet. Se feilmeldingen over. Forste oppstart krever internett.
pause
exit /b 1
