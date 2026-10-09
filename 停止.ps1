$ErrorActionPreference = 'Stop'
$stateFile = Join-Path $PSScriptRoot 'outputs\server-state.json'
if (-not (Test-Path -LiteralPath $stateFile)) { Write-Host '没有记录到运行中的服务。'; exit }
$serverState = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
$serverProcess = Get-Process -Id $serverState.processId -ErrorAction SilentlyContinue
$recordedStart = ([datetime]$serverState.startedAt).ToUniversalTime().ToString('o')
if ($serverProcess -and $serverProcess.Path -eq $serverState.executable -and $serverProcess.StartTime.ToUniversalTime().ToString('o') -eq $recordedStart) {
    Stop-Process -Id $serverProcess.Id
    Write-Host '工作台服务已停止。'
} else { Write-Host '原服务已经退出。' }
