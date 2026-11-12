$Root = Split-Path -Parent $PSScriptRoot
Set-Location "$Root\backend"
.\.venv\Scripts\Activate.ps1
New-Item -ItemType Directory -Force -Path .\data | Out-Null
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
