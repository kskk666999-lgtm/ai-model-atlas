# 一键部署到 GitHub Pages（唯一前置：完成一次 GitHub 登录）
# 用法：powershell -ExecutionPolicy Bypass -File scripts/deploy.ps1 [-RepoName ai-model-atlas]
# 登录方式（二选一，脚本会引导）：
#   A. winget install GitHub.cli 然后 gh auth login   （推荐）
#   B. 已有 Token：$env:GITHUB_TOKEN = "ghp_xxx" 后运行本脚本
param(
    [string]$RepoName = "ai-model-atlas"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Get-Token {
    if ($env:GITHUB_TOKEN) { return $env:GITHUB_TOKEN }
    try {
        $out = "protocol=https`nhost=github.com`n" | git credential fill 2>$null
        $t = ($out | Select-String "^password=(.+)$").Matches.Groups[1].Value
        if ($t) { return $t }
    } catch { }
    return $null
}

$token = Get-Token
if (-not $token) {
    Write-Host "== 需要一次 GitHub 登录（仅此一步需要你操作）==" -ForegroundColor Yellow
    Write-Host "方式 A（推荐）: 在另一个终端执行：" -ForegroundColor Cyan
    Write-Host "    winget install --id GitHub.cli"
    Write-Host "    gh auth login   # 选 GitHub.com -> HTTPS -> Login with a web browser"
    Write-Host "方式 B: 设置环境变量后重跑本脚本：" -ForegroundColor Cyan
    Write-Host '    $env:GITHUB_TOKEN = "你的PAT（需 repo + workflow 权限）"'
    exit 2
}

$api = "https://api.github.com"
$authHeaders = @{ Authorization = "Bearer $token"; Accept = "application/vnd.github+json" }

# 1. 确定用户名
$user = (Invoke-RestMethod -Headers $authHeaders -Uri "$api/user").login
Write-Host "[1/8] GitHub 账号: $user" -ForegroundColor Green

# 2. 创建/复用公开仓库
$repoApi = "$api/repos/$user/$RepoName"
try {
    Invoke-RestMethod -Headers $authHeaders -Uri $repoApi | Out-Null
    Write-Host "[2/8] 仓库已存在: $user/$RepoName" -ForegroundColor Green
} catch {
    Write-Host "[2/8] 创建公开仓库 $user/$RepoName ..."
    $body = @{ name = $RepoName; description = "AI 模型天梯 —— 纯静态全球 AI 模型能力可视化排行榜（无大模型运行时）"; private = $false; has_issues = $true; has_wiki = $false } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Headers $authHeaders -Uri "$api/user/repos" -Body $body -ContentType "application/json" | Out-Null
}

# 3. 设置远程并推送
$remote = "https://github.com/$user/$RepoName.git"
$existing = git remote get-url origin 2>$null
if ($existing -ne $remote) {
    git remote remove origin 2>$null
    git remote add origin $remote
}
Write-Host "[3/8] 推送 main 分支 ..."
git push -u origin main 2>&1 | Select-Object -Last 1

# 4. 开启 Actions 写权限（工作流需要）
try {
    Invoke-RestMethod -Method Put -Headers $authHeaders -Uri "$api/repos/$user/$RepoName/actions/permissions/workflow" -Body '{"default_workflow_permissions":"write","can_approve_pull_request_reviews":false}' -ContentType "application/json"
    Write-Host "[4/8] Actions 读写权限已开启" -ForegroundColor Green
} catch { Write-Host "[4/8] 权限设置跳过（可能已配置）" -ForegroundColor Yellow }

# 5. Pages 来源设为 GitHub Actions
try {
    Invoke-RestMethod -Method Post -Headers $authHeaders -Uri "$api/repos/$user/$RepoName/pages" -Body '{"build_type":"workflow"}' -ContentType "application/json" | Out-Null
    Write-Host "[5/8] Pages 来源 = GitHub Actions" -ForegroundColor Green
} catch {
    try {
        Invoke-RestMethod -Method Put -Headers $authHeaders -Uri "$api/repos/$user/$RepoName/pages" -Body '{"build_type":"workflow"}' -ContentType "application/json" | Out-Null
        Write-Host "[5/8] Pages 来源 = GitHub Actions（更新）" -ForegroundColor Green
    } catch { Write-Host "[5/8] Pages 配置稍后由部署工作流自动完成" -ForegroundColor Yellow }
}

# 6. 触发首次数据更新与部署
$null = Invoke-RestMethod -Method Post -Headers $authHeaders -Uri "$api/repos/$user/$RepoName/actions/workflows/update-data.yml/dispatches" -Body '{"ref":"main"}' -ContentType "application/json"
$null = Invoke-RestMethod -Method Post -Headers $authHeaders -Uri "$api/repos/$user/$RepoName/actions/workflows/deploy-pages.yml/dispatches" -Body '{"ref":"main"}' -ContentType "application/json"
Write-Host "[6/8] 已触发 update-data 与 deploy-pages 工作流" -ForegroundColor Green

# 7. 等待部署完成
$pagesUrl = "https://$user.github.io/$RepoName/"
Write-Host "[7/8] 等待部署完成（约 2~4 分钟）... $pagesUrl"
$deadline = (Get-Date).AddMinutes(8)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 20
    try {
        $runs = Invoke-RestMethod -Headers $authHeaders -Uri "$api/repos/$user/$RepoName/actions/workflows/deploy-pages.yml/runs?per_page=1"
        $status = $runs.workflow_runs[0].status
        $conclusion = $runs.workflow_runs[0].conclusion
        Write-Host "    deploy-pages: $status / $conclusion"
        if ($status -eq "completed") { break }
    } catch { Write-Host "    等待中..." }
}

# 8. 验证站点可访问
try {
    $code = (Invoke-WebRequest -Uri $pagesUrl -UseBasicParsing -TimeoutSec 20).StatusCode
} catch { $code = 0 }
if ($code -eq 200) {
    Write-Host "[8/8] ✅ 网站已上线: $pagesUrl" -ForegroundColor Green
} else {
    Write-Host "[8/8] 站点尚未就绪（Pages 首次部署可能需要几分钟），稍后手动打开: $pagesUrl" -ForegroundColor Yellow
    Write-Host "      工作流状态: https://github.com/$user/$RepoName/actions"
}
Write-Host ""
Write-Host "部署结果已记录到 DEPLOYMENT_RESULT.md（请把实际 URL 填入）" -ForegroundColor Cyan
