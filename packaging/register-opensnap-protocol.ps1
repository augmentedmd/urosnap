# One-time helper: register opensnap:// so the Cloudflare UI "Start local service"
# button can launch OpenSnap.exe. Prefer running OpenSnap.exe once (it self-registers);
# use this script if IT needs an explicit registration step.
#
# Usage (from the extracted OpenSnap folder, or pass -ExePath):
#   .\register-opensnap-protocol.ps1
#   .\register-opensnap-protocol.ps1 -ExePath "C:\OpenSnap\OpenSnap.exe"

param(
  [Parameter(Mandatory = $false)]
  [string]$ExePath
)

$ErrorActionPreference = "Stop"

if (-not $ExePath) {
  $beside = Join-Path $PSScriptRoot "OpenSnap.exe"
  $sibling = Join-Path (Split-Path $PSScriptRoot -Parent) "OpenSnap\OpenSnap.exe"
  $here = Join-Path (Get-Location) "OpenSnap.exe"
  foreach ($candidate in @($beside, $sibling, $here)) {
    if (Test-Path $candidate) {
      $ExePath = (Resolve-Path $candidate).Path
      break
    }
  }
}

if (-not $ExePath -or -not (Test-Path $ExePath)) {
  throw "OpenSnap.exe not found. Pass -ExePath to the extracted OpenSnap.exe."
}

$ExePath = (Resolve-Path $ExePath).Path
$command = "`"$ExePath`" `"%1`""
$root = "HKCU:\Software\Classes\opensnap"

New-Item -Path $root -Force | Out-Null
Set-ItemProperty -Path $root -Name "(default)" -Value "URL:OpenSnap Protocol"
New-ItemProperty -Path $root -Name "URL Protocol" -Value "" -PropertyType String -Force | Out-Null

$icon = Join-Path $root "DefaultIcon"
New-Item -Path $icon -Force | Out-Null
Set-ItemProperty -Path $icon -Name "(default)" -Value "$ExePath,0"

$cmdKey = Join-Path $root "shell\open\command"
New-Item -Path $cmdKey -Force | Out-Null
Set-ItemProperty -Path $cmdKey -Name "(default)" -Value $command

Write-Host "Registered opensnap:// → $ExePath"
Write-Host "Test: start msedge opensnap://start   (or use the Cloudflare UI button)"
