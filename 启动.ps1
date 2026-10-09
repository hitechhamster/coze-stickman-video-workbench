$ErrorActionPreference = 'Stop'
$projectFolder = $PSScriptRoot
$taskPython = Join-Path $projectFolder '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw '请先运行安装.bat，准备运行环境。' }
if (-not (Test-Path -LiteralPath (Join-Path $projectFolder 'frontend\dist\index.html'))) { throw '界面尚未构建，请先运行安装.bat。' }
$outputFolder = Join-Path $projectFolder 'outputs'
New-Item -ItemType Directory -Force -Path $outputFolder | Out-Null
$ready = $false
try {
    $result = Invoke-RestMethod -Uri 'http://127.0.0.1:8010/workflow/profile' -TimeoutSec 2
    $ready = $result.source_name -eq 'huochairenzhongwenclark'
} catch { }
if (-not $ready) {
    $serverProcess = Start-Process -FilePath $taskPython -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8010') -WorkingDirectory (Join-Path $projectFolder 'backend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $outputFolder 'server.out.log') -RedirectStandardError (Join-Path $outputFolder 'server.err.log')
    @{ processId = $serverProcess.Id; startedAt = $serverProcess.StartTime.ToUniversalTime().ToString('o'); executable = $taskPython } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $outputFolder 'server-state.json') -Encoding utf8
    for ($attempt = 0; $attempt -lt 25; $attempt++) {
        Start-Sleep -Milliseconds 200
        try {
            $result = Invoke-RestMethod -Uri 'http://127.0.0.1:8010/workflow/profile' -TimeoutSec 1
            if ($result.source_name -eq 'huochairenzhongwenclark') { $ready = $true; break }
        } catch { }
        if ($serverProcess.HasExited) { break }
    }
}
if (-not $ready) { throw '服务启动失败，请查看 outputs\server.err.log。' }
Write-Host '工作台已启动：http://127.0.0.1:8010/ui/'
if ($env:COZE_NO_BROWSER -ne '1') { Start-Process 'http://127.0.0.1:8010/ui/' -WindowStyle Hidden }
