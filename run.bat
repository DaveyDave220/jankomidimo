@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment not found. Run setup.bat first.
    exit /b 1
)

call ".venv\Scripts\activate.bat"
python ".\src\janko_keyboard.py"

endlocal
