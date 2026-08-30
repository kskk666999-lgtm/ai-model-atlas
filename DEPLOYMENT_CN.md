# 部署指南（Windows 用户版）

从零到上线全部免费，不需要任何服务器。整个过程分两部分：**部署网站** 和 **开启自动更新**。

## 前置条件

- 一个 GitHub 账号
- 本机已安装 Node.js 22 与 Python 3.13（`scripts/bootstrap.ps1` 会检查）

## 第一部分：把项目推上 GitHub

1. 在 GitHub 上新建一个仓库，例如 `ai-model-atlas`（Public，免费 Pages 需要 Public 仓库；Pro 私有仓库也可以）。
2. 在项目根目录打开 PowerShell：

```powershell
git init
git add .
git commit -m "feat: AI 模型天梯初始版本"
git branch -M main
git remote add origin https://github.com/<你的用户名>/ai-model-atlas.git
git push -u origin main
```

## 第二部分：开启 GitHub Pages（网站自动构建部署）

1. 打开仓库页面 → **Settings** → 左侧 **Actions** → **General**：
   - 找到 *Workflow permissions*，选择 **Read and write permissions**，保存。
   （这一步是给自动更新工作流提交数据用的）
2. **Settings** → 左侧 **Pages**：
   - *Build and deployment* 下的 **Source** 选择 **GitHub Actions**。
3. 打开仓库的 **Actions** 页签：
   - 左侧选择 **deploy-pages** 工作流 → 右侧 **Run workflow** → 手动跑一次。
4. 等 1~2 分钟，回到 **Settings → Pages**，顶部会显示网站地址：
   `https://<你的用户名>.github.io/ai-model-atlas/`

> base 路径已自动适配：构建时工作流会传入 `--base=/ai-model-atlas/`，无需手动配置。

## 第三部分：开启每日两次的自动数据更新

1. 打开仓库 **Actions** 页签 → 左侧 **update-data** → **Run workflow** → 手动跑第一次。
   - 跑完后 `public/data/` 下的数据会自动提交，Pages 会自动重新部署。
2. 之后该工作流会按计划每日自动运行两次（UTC 01:00 / 13:00 ≈ 北京时间 09:00 / 21:00；定时任务并非绝对准点，平台高峰期可能略有延迟）。

### 可选：接入 Artificial Analysis（价格/速度/延迟榜）

1. 到 https://artificialanalysis.ai 申请免费数据 API Key（每天限 1000 次请求）。
2. 仓库 **Settings** → **Secrets and variables** → **Actions** → **New repository secret**：
   - Name 填 `AA_API_KEY`，Value 填你的 Key。
3. 重跑一次 **update-data**。
4. 不配置这个 Key 也完全不影响其他榜单，相关能力会显示"数据接入中"。

## 第四部分：Cloudflare Pages（备选方案，可选）

1. 登录 https://dash.cloudflare.com → **Workers & Pages** → **Create** → **Pages** → **Connect to Git**，选择你的仓库。
2. 构建配置：
   - Framework preset：`Vite`
   - Build command：`npm run build`
   - Build output directory：`dist`
3. 保存并部署。之后每次 `main` 分支更新（包括数据自动提交）都会自动重新部署。
4. Cloudflare Pages 直接用根路径，无需 base 配置。

## 日常检查清单

- 仓库 **Actions** 页签：三个工作流（ci / update-data / deploy-pages）均为绿色
- 网站首页右侧"自动更新状态面板"：显示最近一次更新时间与健康的来源数
- **数据来源**页面：所有来源状态为"正常"（个别显示"降级（使用上次数据）"也正常，代表该来源临时失败并已回退）
- 若数据超过 3 天未更新，面板会出现过期提示，去 Actions 手动重跑 update-data 即可

## 常见问题

**Q：第一次 update-data 失败了怎么办？**
打开失败的 workflow run 查看日志。个别来源网络失败不影响整体（流水线按来源隔离失败，保留上次成功数据）。如果 GitHub API 限流，等一小时再手动触发。

**Q：某个模型的名字没被合并怎么办？**
看 `data/reports/unmapped-models.json`，把原始名称加进 `data/registry/aliases.yml` 指向正确的 canonical_id，提交后等下一次更新（或手动触发）。同名不同版本千万不要指向同一个模型。

**Q：想本地预览生产构建？**
`powershell -ExecutionPolicy Bypass -File scripts/build.ps1` 然后 `npm run preview`。
