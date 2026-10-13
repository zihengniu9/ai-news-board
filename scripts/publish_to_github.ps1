# One-time: create the public repo zihengniu9/ai-news-board, turn on Pages (source: GitHub Actions), push, run once.
# Needs GitHub CLI (winget install GitHub.cli) and `gh auth login` done once.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repo
$name = 'zihengniu9/ai-news-board'
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw '没有找到 GitHub CLI。先运行：winget install GitHub.cli ，再运行：gh auth login' }
gh auth status *> $null
if ($LASTEXITCODE -ne 0) { throw 'GitHub CLI 尚未登录。先运行：gh auth login' }

gh repo view $name --json name *> $null
if ($LASTEXITCODE -ne 0) {
    gh repo create $name --public --description 'AI 消息看板：每 4 小时自动采集，GitHub Pages 发布'
    if ($LASTEXITCODE -ne 0) { throw '创建仓库失败' }
}
if (-not ((git remote) -contains 'origin')) { git remote add origin "https://github.com/$name.git" }

# Pages must use "GitHub Actions" as its source before the first deploy.
gh api -X POST "repos/$name/pages" -f build_type=workflow *> $null
if ($LASTEXITCODE -ne 0) { gh api -X PUT "repos/$name/pages" -f build_type=workflow *> $null }
if ($LASTEXITCODE -ne 0) { Write-Warning '未能自动开启 Pages：请到仓库 Settings → Pages，把 Source 选为 GitHub Actions。' }

git push -u origin main
if ($LASTEXITCODE -ne 0) { throw '推送失败' }
Write-Output '已推送。首次推送会自动采集一次并发布页面，约 2–5 分钟。'
Start-Sleep -Seconds 5
gh run list --repo $name --limit 1
Write-Output ("页面地址：https://zihengniu9.github.io/ai-news-board/")
Write-Output ("运行记录：https://github.com/$name/actions")
