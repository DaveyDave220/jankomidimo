@echo off
setlocal
cd /d "%~dp0"

echo This setup prepares the Python environment needed to run the application.
echo uv is a tool that creates that environment and installs the required packages for you.
echo You can also create and manage the Python virtual environment yourself if you prefer.
echo.

where uv >nul 2>&1
if not errorlevel 1 (
    set "UV=uv"
) else (
    echo uv is not installed.
    choice /M "Install uv now"
    if errorlevel 2 (
        echo Setup cancelled.
        exit /b 1
    )

    echo Installing uv...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    set "UV=%USERPROFILE%\.local\bin\uv.exe"
    if not exist "%USERPROFILE%\.local\bin\uv.exe" (
        echo uv installation failed, or its executable could not be found.
        pause
        exit /b 1
    )
)

echo Creating the virtual environment and installing dependencies...
"%UV%" sync
if errorlevel 1 (
    echo Setup failed.
    pause
    exit /b 1
)

echo Setup complete. Run run.bat to start jankomidimo.
echo.
pause
endlocal
