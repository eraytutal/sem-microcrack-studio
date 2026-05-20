@echo off
setlocal

cd /d "%~dp0"

echo.
echo SEM Microcrack Studio - Windows setup
echo =====================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found.
    echo Install Python for Windows, then run this setup script again.
    echo.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to create the virtual environment.
        pause
        exit /b 1
    )
) else (
    echo Existing virtual environment found.
)

echo.
echo Installing dependencies from requirements.txt...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo.
    echo ERROR: Failed to update pip.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo Creating local data and log folders...
if not exist "data" mkdir "data"
if not exist "data\annotations" mkdir "data\annotations"
if not exist "data\predictions" mkdir "data\predictions"
if not exist "data\exports" mkdir "data\exports"
if not exist "logs" mkdir "logs"

echo.
echo Setup complete.
echo Use run_app.bat to start SEM Microcrack Studio.
echo.
pause
