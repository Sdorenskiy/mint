@echo off
rem Zapusk MINT v Windows: dvojnoj shchelchok ili run_mint.bat v konsoli.
rem Stranica otkroetsya v brauzere: http://localhost:8501. Ostanovit - zakrojte eto okno.
cd /d "%~dp0"
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY (where py >nul 2>nul && set "PY=py -3")
if not defined PY set "PY=python"
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>nul || (echo MINT: Python 3.10+ is required, see docs\INSTALL.md & pause & exit /b 1)
%PY% -c "import streamlit" 2>nul || (echo MINT: packages are not installed - run install.bat first & pause & exit /b 1)
echo MINT is starting: http://localhost:8501  (close this window to stop)
start "" /b cmd /c "timeout /t 5 /nobreak >nul & start http://localhost:8501"
%PY% -m streamlit run app.py %*
pause
