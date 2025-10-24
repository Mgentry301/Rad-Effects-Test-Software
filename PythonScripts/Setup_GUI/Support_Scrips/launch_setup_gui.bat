@echo off
setlocal

REM Determine this script directory and repo root
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%..\..\..\.." >nul 2>&1
set "REPO_ROOT=%CD%"
popd >nul 2>&1

REM Resolve Python interpreter (prefer pythonw.exe)
set "PYTHON_EXE=C:\Program Files\Python313\pythonw.exe"
if exist "%PYTHON_EXE%" goto have_python
set "PYTHON_EXE=C:\Program Files\Python313\python.exe"
if exist "%PYTHON_EXE%" goto have_python
where pythonw.exe >nul 2>&1 && for /f "delims=" %%I in ('where pythonw.exe') do set "PYTHON_EXE=%%I" & goto have_python
where python.exe >nul 2>&1 && for /f "delims=" %%I in ('where python.exe') do set "PYTHON_EXE=%%I" & goto have_python
echo Could not find Python. Update Support_Scrips\launch_setup_gui.bat.
pause
exit /b 1

:have_python
set "GUI_SCRIPT=%~dp0..\setup_gui.py"
if not exist "%GUI_SCRIPT%" (
  echo GUI script not found: %GUI_SCRIPT%
  pause
  exit /b 1
)

REM Work in repo root so relative paths resolve
pushd "%REPO_ROOT%" >nul 2>&1
"%PYTHON_EXE%" "%GUI_SCRIPT%"
set EXITCODE=%ERRORLEVEL%
popd >nul 2>&1
exit /b %EXITCODE%
