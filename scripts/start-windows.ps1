$Root = Split-Path -Parent $PSScriptRoot
Set-Location "$Root\backend"
if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) {
  Write-Host "Create a venv first: python -m venv .venv && .\.venv\Scripts\pip install -r requirements.txt"
  exit 1
}
.\.venv\Scripts\Activate.ps1
New-Item -ItemType Directory -Force -Path .\data | Out-Null
# Dev equivalent of OpenSnap.exe — starts API+UI and opens the browser
python -m app.desktop @args
