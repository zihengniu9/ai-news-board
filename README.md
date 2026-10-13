# AI 消息看板（消息台）

个人 AI 选题看板：采集官方产品发布、活动和媒体报道，每 4 小时自动更新。

- **云端（主）**：GitHub Actions 每 4 小时采集一次，结果发布到 GitHub Pages。电脑关机也照常运行。
- **本机（备用）**：`http://127.0.0.1:8766/`，登录自动启动，可手动刷新。本机不再定时采集。

## 目录

| 内容 | 位置 |
| --- | --- |
| 页面、样式、交互 | `site/` |
| 产品与活动采集 | `ai_news_pipeline/board.py` |
| 媒体热度采集 | `ai_news_pipeline/media.py` |
| 网络访问（云端直连 / 本机 TUN） | `ai_news_pipeline/board_network.py` |
| 信源配置 | `config/` |
| 定时任务 | `.github/workflows/collect.yml` |
| 本机服务 | `scripts/serve_news_board.py`、`scripts/install_local.ps1` |

## 云端数据放在哪里

- 数据库和每轮运行记录在 `state` 分支，每次运行覆盖成一个提交，不会让仓库越来越大。
- 每轮的网页原文和数据库备份作为 Actions 运行附件保留 7 天（仓库 → Actions → 某次运行 → Artifacts）。
- `site/board-data.js`、`site/media-data.js` 每次运行时生成，不提交到 `main`。

## 网络规则

- 本机：先验证 Meta TUN 默认路由和代理监听，再经代理用 HTTPS 采集（`AI_NEWS_NETWORK=tun`，默认）。
- 云端：GitHub 的海外服务器直接用 HTTPS 访问来源（`AI_NEWS_NETWORK=direct`），不需要也不检查 TUN。
- 两边都只用 HTTPS、遵守 robots.txt、不绕过登录或访问限制、不使用 WebSocket；瞬态错误最多重试一次。

## 常用操作

- 立即采集一次：仓库 → Actions → Collect and publish → Run workflow。
- 采集失败：该次运行标红，GitHub 会发邮件；页面保留上次数据并在超过 8 小时未成功时变黄。
- 公开仓库超过 60 天没有活动时，GitHub 会暂停定时任务并提前发邮件，点一下即可恢复。
- 收藏和笔记保存在浏览器本地，本机地址和 Pages 地址互不相通，需要用"导出选题清单"自行搬运。
