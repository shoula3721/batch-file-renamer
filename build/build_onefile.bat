@echo off
setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo Create it first:  python -m venv .venv
    pause
    exit /b 1
)

".venv\Scripts\python.exe" build\build.py --target onefile
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. See the log above.
    pause
    exit /b 1
)

echo.
echo Done. Check the "dist" folder.
pause
