@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    set "PYTHON_CMD=python"
)
if not exist .venv (
    echo Preparing the application for first use...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto :error
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 goto :error
)
start "Print Order Manager" .venv\Scripts\pythonw.exe app.py
exit /b 0
:error
echo Setup failed. Verify that Python 3 is installed and try again.
pause
exit /b 1
