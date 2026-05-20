@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Please run setup_windows.bat first.
    echo.
    pause
    exit /b 1
)

if not exist "logs" mkdir "logs"

echo Starting SEM Microcrack Studio...
".venv\Scripts\python.exe" app.py > "logs\app_run.log" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo SEM Microcrack Studio exited with an error.
    echo See logs\app_run.log for details.
    echo.
    pause
    exit /b %EXIT_CODE%
)

exit /b 0
