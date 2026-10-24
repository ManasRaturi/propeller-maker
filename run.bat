@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "PROJECT_DIR=%~dp0"
set "VENV_DIR="
cd /d "%PROJECT_DIR%"
if errorlevel 1 goto directory_error

rem Reuse a portable local environment without requiring Python on PATH.
if exist "%PROJECT_DIR%venv\Scripts\python.exe" set "VENV_DIR=%PROJECT_DIR%venv"
if not defined VENV_DIR if exist "%PROJECT_DIR%.venv\Scripts\python.exe" set "VENV_DIR=%PROJECT_DIR%.venv"
if defined VENV_DIR goto verify_environment

set "VENV_DIR=%PROJECT_DIR%venv"
echo [SETUP] Creating the project Python environment...
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3.12 -c "pass" >nul 2>nul
if not errorlevel 1 (
    py -3.12 -m venv "%VENV_DIR%"
    if errorlevel 1 goto setup_error
    goto install_dependencies
)
py -3 -m venv "%VENV_DIR%"
if errorlevel 1 goto setup_error
goto install_dependencies

:use_python
where python >nul 2>nul
if errorlevel 1 goto missing_python
python -m venv "%VENV_DIR%"
if errorlevel 1 goto setup_error
goto install_dependencies

:verify_environment
rem A failed first install is retried; healthy existing environments need no pip.
if exist "%VENV_DIR%\.propeller-ready" goto launch
"%VENV_DIR%\Scripts\python.exe" -c "import cadquery, customtkinter, numpy, matplotlib, scipy" >nul 2>nul
if errorlevel 1 goto install_dependencies
goto mark_ready

:install_dependencies
echo [SETUP] Installing requirements into the project environment...
"%VENV_DIR%\Scripts\python.exe" -m pip --disable-pip-version-check install -r "%PROJECT_DIR%requirements.txt"
if errorlevel 1 goto dependency_error
"%VENV_DIR%\Scripts\python.exe" -c "import cadquery, customtkinter, numpy, matplotlib, scipy"
if errorlevel 1 goto dependency_error

:mark_ready
>"%VENV_DIR%\.propeller-ready" echo Dependencies verified.

:launch
if /i "%~1"=="--check" (
    echo [OK] Project environment is ready.
    exit /b 0
)
echo [INFO] Starting Propeller CAD...
"%VENV_DIR%\Scripts\python.exe" "%PROJECT_DIR%main.py" %*
set "LAUNCH_EXIT=%ERRORLEVEL%"
if not "%LAUNCH_EXIT%"=="0" (
    echo [ERROR] Application exited with code %LAUNCH_EXIT%.
    pause
)
exit /b %LAUNCH_EXIT%

:missing_python
echo [ERROR] Python was not found. Install Python 3.12 and enable its launcher or PATH entry.
pause
exit /b 1

:directory_error
echo [ERROR] Could not open the project folder.
pause
exit /b 1

:setup_error
echo [ERROR] Could not create the project Python environment.
pause
exit /b 1

:dependency_error
echo [ERROR] Dependency setup did not finish. Check the message above, then run this launcher again.
pause
exit /b 1
