# AI 消息看板（消息台）

个人 AI 选题看板：采集官方产品发布、活动和媒体报道，每 4 小时自动更新。

- 在线看板：https://zihengniu9.github.io/ai-news-board/
- 采集与发布记录：https://github.com/zihengniu9/ai-news-board/actions
- 2026-10-13 首次真实云端采集与发布通过：产品来源 9/9，媒体来源 5/6（机器之心主动停用）；15 个 Python 测试和热度测试通过。公开页面、热度页、手机布局及本机备用入口已验证。

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

- 数据库和每轮运行记录在 `state` 分支，每次发布一个新的单提交快照。数据库本身仍会随历史积累增长，旧 Git 对象的回收由 GitHub 管理。
- 每轮的网页原文和数据库备份作为 Actions 运行附件保留 7 天（仓库 → Actions → 某次运行 → Artifacts）。
- `site/board-data.js`、`site/media-data.js` 每次运行时生成，不提交到 `main`。

## 网络规则

- 本机：先验证 Meta TUN 默认路由和代理监听，再经代理用 HTTPS 采集（`AI_NEWS_NETWORK=tun`，默认）。
- 云端：GitHub 的海外服务器直接用 HTTPS 访问来源（`AI_NEWS_NETWORK=direct`），不需要也不检查 TUN。
- 两边都只用 HTTPS、遵守 robots.txt、不绕过登录或访问限制、不使用 WebSocket；瞬态错误最多重试一次。

## 常用操作

- 立即采集一次：仓库 → Actions → Collect and publish → Run workflow。
- 采集失败：该次运行标红；是否收到邮件取决于你的 GitHub Actions 通知设置。页面保留已采集的数据，并在超过 8 小时未成功时变黄。
- 公开仓库超过 60 天没有活动时，GitHub 会暂停定时任务并提前发邮件，点一下即可恢复。
- 收藏和笔记保存在浏览器本地，本机地址和 Pages 地址互不相通，需要用"导出选题清单"自行搬运。
