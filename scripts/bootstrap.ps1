# 一键初始化 + 启动：检查环境 -> 装依赖 -> 抓真实数据 -> 启动开发服务器
# 运行方式：powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "== AI 模型天梯 · 环境初始化 ==" -ForegroundColor Cyan

# 1. 检查 Node.js
try {
    $node = (node -v) 2>$null
    if ($node -notmatch "^v22\." -and $node -notmatch "^v2[0-9]\.") {
        Write-Host "  [警告] 推荐 Node.js 22，当前为 $node（仍可尝试继续）" -ForegroundColor Yellow
    } else {
        Write-Host "  [OK] Node.js $node"
    }
} catch {
    Write-Host "  [错误] 未检测到 Node.js，请先安装 Node.js 22 LTS: https://nodejs.org" -ForegroundColor Red
    exit 1
}

# 2. 检查 Python（优先 py 启动器的 3.13，其次 python）
$py = $null
try {
    $null = py -3.13 -c "print(1)" 2>$null
    $py = "py -3.13"
} catch {
    try {
        $v = (python --version) 2>$null
        if ($v -match "3\.(11|12|13)") { $py = "python" }
    } catch { }
}
if (-not $py) {
    Write-Host "  [错误] 未检测到 Python 3.11+，请先安装 Python 3.13: https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Python 启动器: $py"

# 3. 创建 Python 虚拟环境并安装依赖
if (-not (Test-Path ".venv")) {
    Write-Host "== 创建 Python 虚拟环境 ==" -ForegroundColor Cyan
    Invoke-Expression "$py -m venv .venv"
}
Write-Host "== 安装 Python 依赖 ==" -ForegroundColor Cyan
.\.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
.\.venv\Scripts\python.exe -m pip install --quiet -r requirements.txt

# 4. 安装前端依赖
Write-Host "== 安装前端依赖 ==" -ForegroundColor Cyan
npm install

# 5. 执行一次真实数据更新（联网）
Write-Host "== 抓取真实榜单数据（首次约 3~5 分钟）==" -ForegroundColor Cyan
.\.venv\Scripts\python.exe -m pipeline.update
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [错误] 数据更新失败（核心校验未通过）。网站仍可启动，但会显示'暂无已验证数据'。" -ForegroundColor Red
    Write-Host "  可重新运行本脚本或 scripts/update-data.ps1 重试。" -ForegroundColor Red
}

# 6. 启动本地开发服务器
Write-Host "== 启动开发服务器 http://localhost:5173 ==" -ForegroundColor Green
npm run dev
