# 生产构建（输出到 dist/，可直接交给 GitHub Pages / Cloudflare Pages）
# 运行方式：powershell -ExecutionPolicy Bypass -File scripts/build.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# 生产构建强制拒绝 DEMO_MODE
if ($env:DEMO_MODE -eq "true") {
    Write-Host "[错误] DEMO_MODE=true 禁止用于生产构建" -ForegroundColor Red
    exit 1
}

npm run build
if ($LASTEXITCODE -eq 0) {
    Write-Host "== 构建完成：dist/ ==" -ForegroundColor Green
    Write-Host "本地预览：npm run preview"
}
