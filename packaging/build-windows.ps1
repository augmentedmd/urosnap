# Build OpenSnap Windows desktop package (onedir with OpenSnap.exe).
# Run on Windows with Python 3.12+ and Node 20+.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "==> Building frontend"
npm --prefix frontend ci
npm --prefix frontend run build

Write-Host "==> Preparing Python packaging venv"
$Venv = Join-Path $Root ".venv-packaging"
if (-not (Test-Path $Venv)) {
  python -m venv $Venv
}
& "$Venv\Scripts\python.exe" -m pip install --upgrade pip
& "$Venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
& "$Venv\Scripts\python.exe" -m pip install -r packaging\requirements-build.txt

Write-Host "==> PyInstaller"
Set-Location backend
& "$Venv\Scripts\pyinstaller.exe" --noconfirm --clean ..\packaging\opensnap.spec
Set-Location $Root

$Dist = Join-Path $Root "backend\dist\OpenSnap"
if (-not (Test-Path (Join-Path $Dist "OpenSnap.exe"))) {
  throw "OpenSnap.exe was not produced"
}

# Optional ffmpeg next to the EXE improves MP4 finalization.
$Ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($Ffmpeg) {
  Copy-Item $Ffmpeg.Source (Join-Path $Dist "ffmpeg.exe") -Force
  Write-Host "Bundled ffmpeg.exe from PATH"
} else {
  Write-Host "ffmpeg not on PATH — AVI fallback will be used until ffmpeg is added beside OpenSnap.exe"
}

$Zip = Join-Path $Root "dist\OpenSnap-windows.zip"
New-Item -ItemType Directory -Force -Path (Split-Path $Zip) | Out-Null
if (Test-Path $Zip) { Remove-Item $Zip -Force }
Compress-Archive -Path $Dist -DestinationPath $Zip
Write-Host "==> Done: $Zip"
Write-Host "Extract and double-click OpenSnap\OpenSnap.exe"
