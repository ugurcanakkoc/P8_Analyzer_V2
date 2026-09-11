@echo off
setlocal
cd /d "%~dp0"
set "UVP_PYTHON=C:\Users\UVW-U\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%UVP_PYTHON%" (
  echo Python bulunamadi. analyzer_v3\README.md dosyasini kontrol edin.
  pause
  exit /b 1
)
if not exist "output\pilots\E122\20260910_v3_p05_rev8\manifest.json" (
  "%UVP_PYTHON%" -m analyzer_v3.prepare
  if errorlevel 1 exit /b 1
)
echo Tarayicida acin: http://127.0.0.1:8765
"%UVP_PYTHON%" -m analyzer_v3.server
if errorlevel 1 pause
