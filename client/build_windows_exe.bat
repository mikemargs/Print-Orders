@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    set "PYTHON_CMD=python"
)
%PYTHON_CMD% -m venv .buildenv
if errorlevel 1 goto :error
.buildenv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :error
.buildenv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name PrintOrderManager-MultiStore app.py
if errorlevel 1 goto :error
echo.
echo EXE created at: dist\PrintOrderManager-MultiStore.exe
echo Install Inno Setup and compile ..\installer\PrintOrderManager.iss for a full installer.
pause
exit /b 0
:error
echo Build failed. Review the message above.
pause
exit /b 1
