@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --collect-data certifi --collect-data discord --hidden-import win32timezone --hidden-import servicemanager --name TaldrisServerStudio app.py
if errorlevel 1 goto fail
echo Ferdig: dist\TaldrisServerStudio.exe
pause
exit /b 0
:fail
echo Bygging feilet. Se feilmeldingen over.
pause
exit /b 1
