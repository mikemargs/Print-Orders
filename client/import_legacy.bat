@echo off
setlocal
cd /d "%~dp0"
set "DEFAULT_DB=%LOCALAPPDATA%\PrintOrderManager\print_orders.db"
echo Import the original single-computer database into this multi-store client.
echo Close both Print Order Manager programs before continuing.
echo.
set /p "STORE=Store number for these orders (5127, 5345, or 3167): "
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe import_legacy.py --database "%DEFAULT_DB%" --store "%STORE%"
) else (
    py -3 import_legacy.py --database "%DEFAULT_DB%" --store "%STORE%"
)
pause
