@echo off
rem Ustanovka MINT v papku .venv ryadom s programmoj (prava administratora ne nuzhny).
rem   install.bat            - pakety iz interneta ili vnutrennego zerkala PyPI (nastrojki pip)
rem   install.bat wheels     - bez interneta, iz oflajn-komplekta (papka wheels, sm. docs\INSTALL.md)
rem   install.bat --clean    - peresozdat .venv s nulya
rem Versii: requirements.lock - tochnye versii, proverennye na GitHub (Windows, Linux; Python 3.10-3.12).
setlocal
cd /d "%~dp0"
rem Python: PYTHON (if set), otherwise the newest of the tested versions via the py launcher, otherwise python
set "PY="
if defined PYTHON set "PY=%PYTHON%"
if not defined PY for %%V in (3.12 3.11 3.10 3.13) do if not defined PY (py -%%V -c "import sys" >nul 2>nul && set "PY=py -%%V")
if not defined PY (where py >nul 2>nul && set "PY=py -3")
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
rem Vyvod pip - v .venv\install.log; na ekrane - tol'ko itog, a pri oshibke - konec zhurnala
set "LOG=.venv\install.log"
type nul > "%LOG%"
set "PIP=.venv\Scripts\python.exe -m pip install --disable-pip-version-check"
if defined WHEELS goto offline
echo Installing packages (%REQ%), a few minutes (first time - about 165 MB) ...
%PIP% -r %REQ% >> "%LOG%" 2>&1 && goto installed
if /i not "%REQ%"=="requirements.lock" goto failed
echo Some exact versions are not available (mirror?) - trying requirements.txt
%PIP% -r requirements.txt >> "%LOG%" 2>&1 && goto installed
goto failed
:offline
echo Installing packages from %WHEELS% ...
%PIP% --no-index --find-links "%WHEELS%" -r %REQ% >> "%LOG%" 2>&1 && goto installed
:failed
echo.
powershell -NoProfile -Command "Get-Content -Tail 25 '%LOG%'"
echo.
echo Installation failed. Full pip output: %CD%\%LOG%
pause
exit /b 1
:installed
if not exist .env (copy .env.example .env >nul & echo Created .env from .env.example - fill in the addresses and key)
rem Samoproverka podskazhet, chto ispravit' (naprimer, adresa v .env); ustanovka pri etom uzhe zavershena
".venv\Scripts\python.exe" check_install.py --no-llm
echo.
echo Done. Start MINT: run_mint.bat
pause
exit /b 0
