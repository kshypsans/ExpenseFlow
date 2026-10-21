@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher not found. Install Python 3.11 or newer from python.org and enable PATH.
  pause
  exit /b 1
)
py -m venv .venv
call .venv\Scripts\activate.bat
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed. Check the error above.
  pause
  exit /b 1
)
echo.
echo Setup complete. Install Tesseract OCR separately, then run run_windows.bat.
pause
