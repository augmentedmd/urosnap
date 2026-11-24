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

# PyInstaller onedir places datas under _internal; also mirror beside the EXE so
# path resolution stays correct if _MEIPASS lookup ever misses.
$BundledUi = Join-Path $Dist "_internal\frontend\dist\index.html"
if (-not (Test-Path $BundledUi)) {
  throw "Packaged UI missing at $BundledUi — npm frontend build was not bundled"
}
$UiBesideExe = Join-Path $Dist "frontend"
if (Test-Path $UiBesideExe) { Remove-Item $UiBesideExe -Recurse -Force }
Copy-Item -Recurse (Join-Path $Dist "_internal\frontend") $UiBesideExe
if (-not (Test-Path (Join-Path $UiBesideExe "dist\index.html"))) {
  throw "Failed to mirror UI beside OpenSnap.exe"
}
Write-Host "Verified UI at _internal\frontend\dist and frontend\dist"

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
# Zip *contents* of the onedir folder so extract yields OpenSnap.exe + deps at
# the archive root (no nested OpenSnap/ wrapper folder).
Compress-Archive -Path (Join-Path $Dist '*') -DestinationPath $Zip

# Fail the build if the zip somehow omits the React shell or nests under OpenSnap/.
Add-Type -AssemblyName System.IO.Compression.FileSystem
$ZipFile = [System.IO.Compression.ZipFile]::OpenRead($Zip)
try {
  $Names = $ZipFile.Entries | ForEach-Object { $_.FullName -replace '\\', '/' }
  $Need = @(
    'OpenSnap.exe',
    '_internal/frontend/dist/index.html',
    'frontend/dist/index.html'
  )
  foreach ($n in $Need) {
    if ($Names -notcontains $n) {
      throw "OpenSnap-windows.zip is missing required top-level path: $n"
    }
  }
  $Nested = $Names | Where-Object { $_ -like 'OpenSnap/*' -or $_ -eq 'OpenSnap/' }
  if ($Nested) {
    throw "OpenSnap-windows.zip still nests under OpenSnap/ — expected flat layout"
  }
} finally {
  $ZipFile.Dispose()
}

Write-Host "==> Done: $Zip"
Write-Host "Extract the zip and double-click OpenSnap.exe (keep _internal beside it)"
