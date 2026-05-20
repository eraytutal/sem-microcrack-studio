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

echo Starting SEM Microcrack Studio in debug mode...
echo Console output will be written to logs\app_debug.log.
echo.

".venv\Scripts\python.exe" app.py > "logs\app_debug.log" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

if exist "logs\app_debug.log" (
    type "logs\app_debug.log"
)

echo.
if not "%EXIT_CODE%"=="0" (
    echo SEM Microcrack Studio exited with error code %EXIT_CODE%.
) else (
    echo SEM Microcrack Studio closed normally.
)
echo.
pause
exit /b %EXIT_CODE%
