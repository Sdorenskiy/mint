@echo off
rem Ustanovka MINT v papku .venv ryadom s programmoj (prava administratora ne nuzhny).
rem   install.bat          - pakety iz interneta ili vnutrennego zerkala PyPI (nastrojki pip)
rem   install.bat wheels   - bez interneta, iz oflajn-komplekta (papka wheels, sm. docs\INSTALL.md)
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY set "PY=python"
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>nul || (echo Python 3.10+ is required: https://www.python.org/downloads/windows/ - "Install for me only", no admin rights needed & pause & exit /b 1)
set "REQ=requirements.txt"
if exist requirements-windows.lock set "REQ=requirements-windows.lock"
if not exist ".venv\Scripts\python.exe" (%PY% -m venv .venv || (echo Failed to create .venv & pause & exit /b 1))
if "%~1"=="" (".venv\Scripts\python.exe" -m pip install -r %REQ%) else (".venv\Scripts\python.exe" -m pip install --no-index --find-links "%~1" -r %REQ%)
if errorlevel 1 (echo Installation failed - see the messages above & pause & exit /b 1)
if not exist .env (copy .env.example .env >nul & echo Created .env from .env.example - fill in the addresses and key)
".venv\Scripts\python.exe" check_install.py --no-llm
echo.
echo Done. Start MINT: run_mint.bat
pause
