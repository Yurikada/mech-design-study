@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run scripts\setup.ps1 first. See README.md.
  exit /b 1
)
if "%~1"=="" (
  ".venv\Scripts\python.exe" -m mech_design cases\heated_cantilever.toml
) else (
  ".venv\Scripts\python.exe" -m mech_design %*
)
exit /b %errorlevel%
