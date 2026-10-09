$ErrorActionPreference = 'Stop'
$projectFolder = $PSScriptRoot
$taskPython = Join-Path $projectFolder '.venv\Scripts\python.exe'
$bundledRoot = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies'
if (-not (Test-Path -LiteralPath $taskPython)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    $bootstrapPython = if ($pythonCommand) { $pythonCommand.Source } else { Join-Path $bundledRoot 'python\python.exe' }
    if (-not (Test-Path -LiteralPath $bootstrapPython)) { throw '请安装 Python 3.10+ 并添加到 PATH。' }
    & $bootstrapPython -m venv (Join-Path $projectFolder '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Python 环境创建失败。' }
}
& $taskPython -m pip install -r (Join-Path $projectFolder 'backend\requirements.txt')
if ($LASTEXITCODE -ne 0) { throw '后端依赖安装失败。' }
$envFile = Join-Path $projectFolder 'backend\.env'
if (-not (Test-Path -LiteralPath $envFile)) { Copy-Item -LiteralPath (Join-Path $projectFolder 'backend\.env.example') -Destination $envFile }
# A prebuilt interface is included; Node is only required when rebuilding from source.
if (-not (Test-Path -LiteralPath (Join-Path $projectFolder 'frontend\dist\index.html'))) {
    Push-Location (Join-Path $projectFolder 'frontend')
    try {
        $npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
        if ($npmCommand) { & $npmCommand.Source install; if ($LASTEXITCODE -eq 0) { & $npmCommand.Source run build } }
        else {
            $pnpmCommand = Join-Path $bundledRoot 'bin\fallback\pnpm.cmd'
            if (-not (Test-Path -LiteralPath $pnpmCommand)) { throw '请安装 Node.js 22.12+，以构建界面。' }
            & $pnpmCommand install
            if ($LASTEXITCODE -eq 0) { & $pnpmCommand run build }
        }
        if ($LASTEXITCODE -ne 0) { throw '界面构建失败。' }
    } finally { Pop-Location }
}
Write-Host '安装完成。运行启动.bat，在服务配置中填写密钥和剪映草稿位置。'
