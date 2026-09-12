@echo off
rem Uvp.PdfToP8.Host derlemesi - yerel EPLAN P8 2026 Bin'e karsi. DLL'ler repoya kopyalanmaz.
rem Kullanim: build.bat [cikti_klasoru]   (varsayilan: ..\..\output\eplan_addin_bin)
setlocal
set "HERE=%~dp0"
set "SRC=%HERE%..\src\Uvp.PdfToP8.Host"
set "OUT=%~1"
if "%OUT%"=="" set "OUT=%HERE%..\..\output\eplan_addin_bin"
if not exist "%OUT%" mkdir "%OUT%"
rem Assembly adi: EPLAN ayni adli assembly'yi tek oturumda ikinci kez yukleyemez.
rem Her derlemede farkli ad -> EPLAN kapatmadan yenileme. Ad verilmezse zaman damgasi.
set "NAME=%~2"
if "%NAME%"=="" for /f %%t in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "NAME=Uvp.PdfToP8.Host_%%t"

set "EPLAN_BIN="
for /d %%v in ("C:\Program Files\EPLAN\Platform\2026*") do if exist "%%v\Bin\Eplan.EplApi.AFu.dll" set "EPLAN_BIN=%%v\Bin"
if "%EPLAN_BIN%"=="" (echo HATA: EPLAN 2026 Bin bulunamadi.& exit /b 1)

set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" (echo HATA: csc.exe yok.& exit /b 1)

"%CSC%" /nologo /target:library /codepage:65001 /out:"%OUT%\%NAME%.dll" ^
  /r:"%EPLAN_BIN%\Eplan.EplApi.AFu.dll" /r:"%EPLAN_BIN%\Eplan.EplApi.Baseu.dll" ^
  /r:"%EPLAN_BIN%\Eplan.EplApi.DataModelu.dll" /r:"%EPLAN_BIN%\Eplan.EplApi.HEServicesu.dll" ^
  /r:"%EPLAN_BIN%\Eplan.EplApi.MasterDatau.dll" /r:System.Web.Extensions.dll ^
  /r:"%EPLAN_BIN%\Microsoft.Web.WebView2.Core.dll" /r:"%EPLAN_BIN%\Microsoft.Web.WebView2.WinForms.dll" ^
  /r:System.Windows.Forms.dll /r:System.Drawing.dll ^
  "%SRC%\*.cs"
if errorlevel 1 (echo DERLEME BASARISIZ& exit /b 1)
echo TAMAM: %OUT%\%NAME%.dll  (EPLAN: %EPLAN_BIN%)
exit /b 0
