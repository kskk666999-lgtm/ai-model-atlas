# DEPLOYMENT_RESULT · 部署结果

> 状态：**待登录部署**（本机无 GitHub 凭据、未装 gh CLI）。
> 除"GitHub 登录"外的一切已就绪；完成登录后运行一条命令即可上线。

## 当前状态

| 项 | 状态 |
|---|---|
| 本地项目路径 | `C:\Users\wjr15\.zcode\workspace\default\ai-model-atlas` |
| Git 仓库 | 已初始化，全部工作已提交（见下方 SHA） |
| GitHub 远程 | 尚未设置（等待登录） |
| Pages 地址 | 部署后为 `https://<你的用户名>.github.io/ai-model-atlas/` |
| 部署自动化 | `scripts/deploy.ps1`（登录后一条命令完成 8 步） |

## 你需要做的唯一一步（约 3 分钟）

打开 PowerShell，执行：

```powershell
winget install --id GitHub.cli -e
gh auth login
```

`gh auth login` 的选择：**GitHub.com → HTTPS → Login with a web browser**，
浏览器里输入屏幕显示的一次性代码并授权。

然后回到项目目录执行：

```powershell
cd C:\Users\wjr15\.zcode\workspace\default\ai-model-atlas
powershell -ExecutionPolicy Bypass -File scripts\deploy.ps1
```

脚本会自动完成：创建公开仓库 `ai-model-atlas` → 推送 main → 开启 Actions 读写权限 →
Pages 来源设为 GitHub Actions → 触发首次 update-data 与 deploy-pages → 轮询等待 →
验证站点 200 → 打印实际访问地址。

（如果你更愿意用 Token：`$env:GITHUB_TOKEN = "ghp_xxx"` 后直接运行 deploy.ps1 也可以，
Token 需要 repo + workflow 权限。）

## 登录后脚本自动完成的 8 步

1. 读取 GitHub 账号
2. 创建公开仓库 `<user>/ai-model-atlas`
3. 推送 main 分支（全部代码 + 数据 + 验收报告）
4. 开启 Actions 读写权限
5. Pages 来源 = GitHub Actions
6. 触发 `update-data`（首次真实数据更新）+ `deploy-pages`
7. 轮询工作流至完成（约 2~4 分钟）
8. 验证 `https://<user>.github.io/ai-model-atlas/` 返回 200

## 上线后 24 小时内会自动发生

- `update-data` 每 12 小时（北京时间约 09:00 / 21:00）自动抓取官方数据并生成静态 JSON；
  数据无变化时不产生提交（幂等输出已验证：连续 4 轮 0 文件变化）
- 数据提交经 push 自动触发 Pages 重新部署

## 上线后请把实际值填进下表

- [ ] 实际 Pages 地址：`https://________.github.io/ai-model-atlas/`
- [ ] 首次 deploy-pages 工作流：`https://github.com/________/ai-model-atlas/actions/runs/________`
- [ ] 首次 update-data 工作流：`https://github.com/________/ai-model-atlas/actions/runs/________`

## 可选配置

- `AA_API_KEY`（解锁价格/速度/延迟榜）：仓库 Settings → Secrets and variables → Actions →
  New repository secret，名称 `AA_API_KEY`；不配置不影响其他榜单
- 手动触发数据更新：仓库 Actions → update-data → Run workflow
