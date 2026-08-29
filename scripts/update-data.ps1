# 只更新数据（联网抓取 + 生成 public/data 下的静态 JSON）
# 运行方式：powershell -ExecutionPolicy Bypass -File scripts/update-data.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path ".venv")) {
    Write-Host "请先运行 scripts/bootstrap.ps1 完成初始化" -ForegroundColor Red
    exit 1
}
Write-Host "== 更新榜单数据（不调用任何大模型 API）==" -ForegroundColor Cyan
.\.venv\Scripts\python.exe -m pipeline.update
if ($LASTEXITCODE -eq 0) {
    Write-Host "== 更新完成，数据已写入 public/data ==" -ForegroundColor Green
} else {
    Write-Host "== 更新失败：核心校验未通过，线上数据未被改动 ==" -ForegroundColor Red
    exit $LASTEXITCODE
}
