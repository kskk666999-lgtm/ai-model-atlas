# 启动本地开发服务器
# 运行方式：powershell -ExecutionPolicy Bypass -File scripts/dev.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path ".venv") -or -not (Test-Path "node_modules")) {
    Write-Host "依赖尚未安装，先执行 bootstrap.ps1 ..." -ForegroundColor Yellow
    powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
    exit 0
}
npm run dev
