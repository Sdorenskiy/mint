@echo off
rem Ustanovka MINT v papku .venv ryadom s programmoj (prava administratora ne nuzhny).
rem   install.bat            - pakety iz interneta ili vnutrennego zerkala PyPI (nastrojki pip)
rem   install.bat wheels     - bez interneta, iz oflajn-komplekta (papka wheels, sm. docs\INSTALL.md)
rem   install.bat --clean    - peresozdat .venv s nulya
rem Versii: requirements.lock - tochnye versii, proverennye na GitHub (Windows, Linux; Python 3.10-3.12).
setlocal
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY set "PY=python"
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>nul || (echo Python 3.10+ is required: https://www.python.org/downloads/windows/ - "Install for me only", no admin rights needed & pause & exit /b 1)
set "REQ=requirements.txt"
if exist requirements-windows.lock set "REQ=requirements-windows.lock"
if exist requirements.lock set "REQ=requirements.lock"
set "WHEELS="
set "CLEAN="
for %%A in (%*) do (if /i "%%~A"=="--clean" (set "CLEAN=1") else (set "WHEELS=%%~fA"))
echo Python: & %PY% --version & echo Packages: %REQ% %WHEELS%
if defined CLEAN if exist .venv rmdir /s /q .venv
rem Nepolnaya .venv (bez pip - naprimer, posle prervannoj pervoj popytki) - sozdaetsya zanovo
if exist ".venv\Scripts\python.exe" (".venv\Scripts\python.exe" -m pip --version >nul 2>nul || (echo Incomplete .venv - recreating & rmdir /s /q .venv))
if not exist ".venv\Scripts\python.exe" (%PY% -m venv .venv || (echo Failed to create .venv & pause & exit /b 1))
if defined WHEELS goto offline
".venv\Scripts\python.exe" -m pip install -r %REQ% && goto installed
if /i not "%REQ%"=="requirements.lock" goto failed
echo Some exact versions are not available (mirror?) - trying requirements.txt
".venv\Scripts\python.exe" -m pip install -r requirements.txt && goto installed
goto failed
:offline
".venv\Scripts\python.exe" -m pip install --no-index --find-links "%WHEELS%" -r %REQ% && goto installed
:failed
echo Installation failed - see the pip messages above
pause
exit /b 1
:installed
if not exist .env (copy .env.example .env >nul & echo Created .env from .env.example - fill in the addresses and key)
".venv\Scripts\python.exe" check_install.py --no-llm
echo.
echo Done. Start MINT: run_mint.bat
pause
