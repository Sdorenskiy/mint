@echo off
rem Obnovlenie MINT na meste iz novoj versii - arhiva .zip ili raspakovannoj papki. Vashi nastrojki ostayutsya:
rem .env, config.yaml, glossary.json, checklists.yaml, prompts.yaml, okruzhenie .venv, baza znanij i logi.
rem   update.bat C:\Users\me\Downloads\mint-21.0.zip     - iz arhiva
rem   update.bat C:\Users\me\Downloads\mint-21.0         - iz papki
rem   update.bat mint-21.0.zip wheels                    - pakety bez interneta (kak install.bat wheels)
rem Snachala ostanovite MINT (zakrojte ego okno).
setlocal
set "SRC=%~f1"
set "WHEELS="
if not "%~2"=="" set "WHEELS=%~f2"
cd /d "%~dp0"
if "%~1"=="" goto usage
set "TMPD="
if /i not "%~x1"==".zip" goto have_src
set "TMPD=%TEMP%\mint_update_%RANDOM%%RANDOM%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%SRC%' -DestinationPath '%TMPD%' -Force"
if errorlevel 1 goto fail_zip
set "SRC=%TMPD%"
:have_src
if not exist "%SRC%\" goto not_found
if exist "%SRC%\mint\version.py" goto found
for /d %%D in ("%SRC%\*") do if exist "%%D\mint\version.py" set "SRC=%%D"
if not exist "%SRC%\mint\version.py" goto not_mint
:found
if /i "%SRC%\"=="%~dp0" goto same
set "OLD=?"
for /f "tokens=2 delims==" %%V in ('findstr /b "MINT_VERSION" mint\version.py 2^>nul') do set "OLD=%%V"
for /f "tokens=2 delims==" %%V in ('findstr /b "MINT_VERSION" "%SRC%\mint\version.py"') do set "NEW=%%V"
set "OLD=%OLD:"=%"
set "NEW=%NEW:"=%"
echo MINT %OLD% -^> %NEW%

rem Papki s kodom zamenyayutsya celikom, ostal'noe kopiruetsya poverh
for %%D in (mint tests tools docs static) do call :replace_dir %%D || goto fail_copy
if exist "%SRC%\.streamlit" robocopy "%SRC%\.streamlit" .streamlit /E /XF secrets.toml /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto fail_copy
if exist "%SRC%\eval" robocopy "%SRC%\eval" eval /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto fail_copy
if not exist "%SRC%\requirements.lock" if exist requirements.lock del requirements.lock
if not exist "%SRC%\requirements-windows.lock" if exist requirements-windows.lock del requirements-windows.lock
robocopy "%SRC%" . /XF .env config.yaml glossary.json checklists.yaml prompts.yaml /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto fail_copy
echo Files updated, your settings kept.

if not defined WHEELS if exist "%SRC%\wheels" set "WHEELS=%SRC%\wheels"
if defined WHEELS (call install.bat "%WHEELS%") else (call install.bat)
if defined TMPD rmdir /s /q "%TMPD%"
exit /b 0

:replace_dir
if not exist "%SRC%\%1" exit /b 0
if exist "%1" rmdir /s /q "%1"
robocopy "%SRC%\%1" "%1" /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 exit /b 1
exit /b 0

:usage
echo Usage: update.bat path\to\mint-new.zip   (or a folder)
pause
exit /b 1
:fail_zip
echo Cannot unpack %SRC%
goto fail
:not_found
echo Not found: %SRC%
goto fail
:not_mint
echo No MINT in %~1 (mint\version.py not found)
goto fail
:same
echo This is the same folder
goto fail
:fail_copy
echo Copy failed - see the messages above
:fail
if defined TMPD rmdir /s /q "%TMPD%"
pause
exit /b 1
