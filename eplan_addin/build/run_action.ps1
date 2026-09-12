# EPLAN P8'yi gizli başlatır, add-in'i kaydeder, verilen action'ı çalıştırır, add-in kaydını
# geri alır. Yalnız KENDİ başlattığı EPLAN sürecini bekler/kapatır; açık bir EPLAN varsa başlamaz.
# Kullanım: run_action.ps1 -Dll <Uvp.PdfToP8.Host.dll> -Action 'UvpPdfToP8Probe /OUT:"..."' -Result <beklenen dosya>
param(
  [Parameter(Mandatory)] [string]$Dll,
  [Parameter(Mandatory)] [string]$Action,
  [Parameter(Mandatory)] [string]$Result,
  [int]$TimeoutSec = 600,
  # Bu makinede kurulu varyant 'Pro Panel' (kullanıcı kısayolu). 'Electric P8' klasörü kurulu değil.
  [string]$Variant = 'Pro Panel'
)
$ErrorActionPreference = 'Stop'
$exe = Get-ChildItem 'C:\Program Files\EPLAN\Platform\2026*\Bin\EPLAN.exe' | Select-Object -First 1 -ExpandProperty FullName
if (-not $exe) { throw 'EPLAN.exe bulunamadı.' }
if (Get-Process -Name EPLAN -ErrorAction SilentlyContinue) { throw 'Açık bir EPLAN var; kullanıcının oturumuna dokunulmaz. Kapatınca tekrar deneyin.' }
if (Test-Path -LiteralPath $Result) { throw 'Sonuç dosyası zaten var; korunuyor. Yeni bir çıktı yolu seçin.' }
$argline = "/Variant:`"$Variant`" /Quiet:1 /NoSplash /NoLoadWorkspace /Frame:0 Auto " +
        "EplApiModuleAction /register:`"$Dll`" $Action EplApiModuleAction /unregister:`"$Dll`""
Write-Output "EPLAN: $exe"
Write-Output "ARGS : $argline"
$p = Start-Process -FilePath $exe -ArgumentList $argline -WindowStyle Hidden -PassThru
$sw = [Diagnostics.Stopwatch]::StartNew()
while (-not $p.HasExited -and $sw.Elapsed.TotalSeconds -lt $TimeoutSec) { Start-Sleep -Seconds 3 }
$state = if ($p.HasExited) { "EXITED code=$($p.ExitCode)" } else { 'TIMEOUT' }
Write-Output "EPLAN $state after $([int]$sw.Elapsed.TotalSeconds)s; result exists: $(Test-Path $Result)"
if (-not $p.HasExited) {
  # Yalnız bizim başlattığımız süreç. Başka EPLAN oturumuna dokunulmaz.
  Stop-Process -Id $p.Id -Force
  Write-Output "Kendi başlattığımız EPLAN (PID $($p.Id)) zaman aşımında kapatıldı."
}
if ($state -eq 'TIMEOUT') { throw 'EPLAN zaman aşımı: işlem sonucu belirsiz; otomatik yeniden denenmez.' }
if (-not (Test-Path -LiteralPath $Result)) { throw 'EPLAN beklenen sonuç dosyasını üretmedi.' }
$resultText = Get-Content -LiteralPath $Result -Raw -Encoding UTF8
$resultData = $resultText | ConvertFrom-Json
$resultText
if ($resultData.ok -eq $false) { throw 'EPLAN raporu başarısız: sonuç dosyasındaki hata ve reddedilenleri inceleyin.' }
