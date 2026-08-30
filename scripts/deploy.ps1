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

    # 优先复用 gh auth login 写入系统凭据库的登录状态，令牌只保留在内存中。
    if (Get-Command gh -ErrorAction SilentlyContinue) {
        try {
            $t = (& gh auth token --hostname github.com 2>$null | Select-Object -First 1)
            if (($LASTEXITCODE -eq 0) -and $t) { return $t.Trim() }
        } catch { }
    }

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
$authHeaders = @{
    Authorization = "Bearer $token"
    Accept = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

# PowerShell 5.1 不可靠地处理命令行中的嵌套 JSON 引号，统一由对象生成 JSON。
$workflowPermissionsBody = @{
    default_workflow_permissions = "write"
    can_approve_pull_request_reviews = $false
} | ConvertTo-Json -Compress
$pagesBody = @{ build_type = "workflow" } | ConvertTo-Json -Compress
$dispatchBody = @{ ref = "main" } | ConvertTo-Json -Compress

function Start-WorkflowDispatch {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkflowFile
    )

    for ($attempt = 1; $attempt -le 6; $attempt++) {
        try {
            $null = Invoke-RestMethod -Method Post -Headers $authHeaders -Uri "$api/repos/$user/$RepoName/actions/workflows/$WorkflowFile/dispatches" -Body $dispatchBody -ContentType "application/json"
            return
        } catch {
            if ($attempt -eq 6) {
                throw "触发 $WorkflowFile 失败：$($_.Exception.Message)"
            }
            Write-Host "    $WorkflowFile 尚未可触发，5 秒后重试（$attempt/6）..."
            Start-Sleep -Seconds 5
        }
    }
}

function Wait-WorkflowRun {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkflowFile,
        [Parameter(Mandatory = $true)]
        [datetime]$NotBefore,
        [string]$HeadSha = "",
        [string]$Event = "",
        [int]$TimeoutMinutes = 30
    )

    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    $lastState = ""
    while ((Get-Date) -lt $deadline) {
        try {
            $runs = Invoke-RestMethod -Headers $authHeaders -Uri "$api/repos/$user/$RepoName/actions/workflows/$WorkflowFile/runs?per_page=20"
            $matchingRuns = @($runs.workflow_runs | Where-Object {
                $createdAt = ([datetime]$_.created_at).ToUniversalTime()
                ($createdAt -ge $NotBefore.ToUniversalTime().AddSeconds(-5)) -and
                ((-not $HeadSha) -or ($_.head_sha -eq $HeadSha)) -and
                ((-not $Event) -or ($_.event -eq $Event))
            })

            if ($matchingRuns.Count -gt 0) {
                $run = $matchingRuns | Sort-Object { ([datetime]$_.created_at).ToUniversalTime() } -Descending | Select-Object -First 1
                $state = "$($run.status)/$($run.conclusion)"
                if ($state -ne $lastState) {
                    Write-Host "    $WorkflowFile : $state"
                    $lastState = $state
                }

                if ($run.status -eq "completed") {
                    if ($run.conclusion -eq "success") {
                        return $run
                    }
                    if ($run.conclusion -ne "cancelled") {
                        throw "$WorkflowFile 失败：$($run.conclusion)；日志：$($run.html_url)"
                    }
                }
            }
        } catch {
            if ($_.Exception.Message -like "$WorkflowFile 失败：*") {
                throw
            }
            Write-Host "    读取 $WorkflowFile 状态失败，继续等待：$($_.Exception.Message)"
        }
        Start-Sleep -Seconds 10
    }

    throw "等待 $WorkflowFile 超时（$TimeoutMinutes 分钟）"
}

function Wait-PagesReady {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PagesUrl,
        [int]$TimeoutMinutes = 10
    )

    $metaUrl = $PagesUrl.TrimEnd("/") + "/data/meta.json"
    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    while ((Get-Date) -lt $deadline) {
        $pageCode = 0
        $metaCode = 0
        try {
            $pageCode = (Invoke-WebRequest -Uri $PagesUrl -UseBasicParsing -TimeoutSec 20).StatusCode
        } catch { }
        try {
            $metaCode = (Invoke-WebRequest -Uri $metaUrl -UseBasicParsing -TimeoutSec 20).StatusCode
        } catch { }

        Write-Host "    Pages HTTP: 首页=$pageCode / 数据=$metaCode"
        if (($pageCode -eq 200) -and ($metaCode -eq 200)) {
            return
        }
        Start-Sleep -Seconds 10
    }

    throw "Pages 在 $TimeoutMinutes 分钟内未同时通过首页和数据检查：$PagesUrl"
}

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
$remoteNames = @(& git remote)
if ($LASTEXITCODE -ne 0) {
    throw "读取 Git 远程列表失败（退出码 $LASTEXITCODE）"
}
$originExists = $remoteNames -contains "origin"
$existing = $null
if ($originExists) {
    $existing = & git remote get-url origin
    if ($LASTEXITCODE -ne 0) {
        throw "读取 origin 失败（退出码 $LASTEXITCODE）"
    }
}
if ($existing -ne $remote) {
    if ($originExists) {
        & git remote set-url origin $remote
    } else {
        & git remote add origin $remote
    }
    if ($LASTEXITCODE -ne 0) {
        throw "设置 origin 失败（退出码 $LASTEXITCODE）"
    }
}
Write-Host "[3/8] 推送 main 分支 ..."
$pushStartedAt = (Get-Date).ToUniversalTime()
& git push -u origin main
$pushExitCode = $LASTEXITCODE
if ($pushExitCode -ne 0) {
    throw "git push 失败（退出码 $pushExitCode）"
}
$initialShaRaw = & git rev-parse HEAD
$revParseExitCode = $LASTEXITCODE
if ($revParseExitCode -ne 0) {
    throw "读取本地提交 SHA 失败（退出码 $revParseExitCode）"
}
$initialSha = ([string]$initialShaRaw).Trim()

# 4. 开启 Actions 写权限（工作流需要）
Invoke-RestMethod -Method Put -Headers $authHeaders -Uri "$api/repos/$user/$RepoName/actions/permissions/workflow" -Body $workflowPermissionsBody -ContentType "application/json" | Out-Null
Write-Host "[4/8] Actions 读写权限已开启" -ForegroundColor Green

# 5. Pages 来源设为 GitHub Actions
$pagesExists = $false
try {
    Invoke-RestMethod -Headers $authHeaders -Uri "$api/repos/$user/$RepoName/pages" | Out-Null
    $pagesExists = $true
} catch { }

if ($pagesExists) {
    Invoke-RestMethod -Method Put -Headers $authHeaders -Uri "$api/repos/$user/$RepoName/pages" -Body $pagesBody -ContentType "application/json" | Out-Null
} else {
    try {
        Invoke-RestMethod -Method Post -Headers $authHeaders -Uri "$api/repos/$user/$RepoName/pages" -Body $pagesBody -ContentType "application/json" | Out-Null
    } catch {
        # 若 Pages 在检查后被并发创建，则改为更新；两次都失败时由 PowerShell 抛出真实错误。
        Invoke-RestMethod -Method Put -Headers $authHeaders -Uri "$api/repos/$user/$RepoName/pages" -Body $pagesBody -ContentType "application/json" | Out-Null
    }
}
Write-Host "[5/8] Pages 来源 = GitHub Actions" -ForegroundColor Green

# 6. 触发首次数据更新。部署必须等数据更新完成后再针对最终 main SHA 触发。
$updateStartedAt = (Get-Date).ToUniversalTime()
Start-WorkflowDispatch -WorkflowFile "update-data.yml"
Write-Host "[6/8] 已触发 update-data 工作流" -ForegroundColor Green

# 7. 等待 CI 与数据更新完成，再部署最终 main。
$pagesUrl = "https://$user.github.io/$RepoName/"
Write-Host "[7/8] 等待 CI、update-data 与最终 Pages 部署 ..."
$ciRun = Wait-WorkflowRun -WorkflowFile "ci.yml" -NotBefore ($pushStartedAt.AddDays(-7)) -HeadSha $initialSha -Event "push"
$updateRun = Wait-WorkflowRun -WorkflowFile "update-data.yml" -NotBefore $updateStartedAt -HeadSha $initialSha -Event "workflow_dispatch" -TimeoutMinutes 55

$finalSha = (Invoke-RestMethod -Headers $authHeaders -Uri "$repoApi/branches/main").commit.sha
$finalDeployStartedAt = (Get-Date).ToUniversalTime()
Start-WorkflowDispatch -WorkflowFile "deploy-pages.yml"
$deployRun = Wait-WorkflowRun -WorkflowFile "deploy-pages.yml" -NotBefore $finalDeployStartedAt -HeadSha $finalSha -Event "workflow_dispatch" -TimeoutMinutes 45

# 8. 验证站点可访问
Wait-PagesReady -PagesUrl $pagesUrl
Write-Host "[8/8] 网站已上线，首页与数据均返回 HTTP 200" -ForegroundColor Green

Write-Host ""
Write-Host "Repository : https://github.com/$user/$RepoName" -ForegroundColor Cyan
Write-Host "Pages      : $pagesUrl" -ForegroundColor Cyan
Write-Host "Commit SHA : $finalSha" -ForegroundColor Cyan
Write-Host "CI         : $($ciRun.status)/$($ciRun.conclusion)" -ForegroundColor Cyan
Write-Host "update-data: $($updateRun.status)/$($updateRun.conclusion)" -ForegroundColor Cyan
Write-Host "deploy-pages: $($deployRun.status)/$($deployRun.conclusion)" -ForegroundColor Cyan
