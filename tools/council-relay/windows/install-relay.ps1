param(
  [string]$RepoPath = "$env:USERPROFILE\Documents\swsi-quiz-backup",
  [string]$WorkspacePath = "$env:LOCALAPPDATA\SWSI\CouncilRelay\workspace",
  [string]$Repository = 'grizzly020503/swsi-quiz-backup'
)

$ErrorActionPreference = 'Stop'
$stateDir = Join-Path $env:LOCALAPPDATA 'SWSI\CouncilRelay'
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Node.js is required.' }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'GitHub CLI (gh) is required.' }
if (-not (Get-Command agy -ErrorAction SilentlyContinue)) { throw 'Antigravity CLI (agy) is required.' }

& gh auth status *> $null
if ($LASTEXITCODE -ne 0) { throw 'GitHub CLI is not authenticated.' }

if (-not (Test-Path (Join-Path $WorkspacePath '.git'))) {
  New-Item -ItemType Directory -Force -Path (Split-Path $WorkspacePath -Parent) | Out-Null
  & gh repo clone $Repository $WorkspacePath
  if ($LASTEXITCODE -ne 0) { throw 'Failed to create the dedicated relay workspace.' }
}

$config = @{
  repository = $Repository
  workspace = $WorkspacePath
  ghCommand = 'gh'
  agyCommand = 'agy'
  pollSeconds = 120
  reviewTimeoutMinutes = 15
  claimTtlMinutes = 120
  maxIssueScan = 100
}
$configPath = Join-Path $stateDir 'config.json'
$config | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $configPath

$startScript = Join-Path $RepoPath 'tools\council-relay\windows\start-relay.ps1'
if (-not (Test-Path $startScript)) { throw "Start script not found: $startScript" }

$actionArgs = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$startScript`" -ConfigPath `"$configPath`" -RepoPath `"$RepoPath`""
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $actionArgs
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName 'SWSI Council Relay' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null

Write-Host "Installed SWSI Council Relay."
Write-Host "Config: $configPath"
Write-Host "Workspace: $WorkspacePath"
Write-Host "Task Scheduler entry: SWSI Council Relay"
Write-Host "No global PowerShell execution policy was changed."
