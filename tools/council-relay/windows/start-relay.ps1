param(
  [string]$ConfigPath = "$env:LOCALAPPDATA\SWSI\CouncilRelay\config.json",
  [string]$RepoPath = "$env:USERPROFILE\Documents\swsi-quiz-backup"
)

$ErrorActionPreference = 'Stop'
$logDir = Join-Path $env:LOCALAPPDATA 'SWSI\CouncilRelay'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir 'relay.log'
$relay = Join-Path $RepoPath 'tools\council-relay\relay.mjs'

if (-not (Test-Path $relay)) {
  Add-Content -Path $logPath -Value "[$(Get-Date -Format o)] Relay script missing: $relay"
  exit 1
}

& node $relay --watch --config $ConfigPath *>> $logPath
