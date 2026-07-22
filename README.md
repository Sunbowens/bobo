# bobo · 观测每日 GitHub 热门项目

一个**零依赖**（仅需 Python 3 标准库）的小工具，用来观测 GitHub 上每天/每周/每月的
热门（trending）项目。可在命令行手动运行，也可通过内置的 GitHub Actions 每天自动
抓取并把榜单归档到 [`reports/`](reports/)。

## 特性

- 🐍 仅依赖 Python 3 标准库，`git clone` 后即可运行，无需 `pip install`
- ⏱️ 支持 `daily` / `weekly` / `monthly` 三种时间范围
- 🔤 支持按编程语言（`--language rust`）与自然语言（`--spoken-language zh`）过滤
- 📄 三种输出格式：控制台表格、Markdown、JSON
- 💬 一键推送到 **Slack**（Incoming Webhook，Block Kit 富文本）
- 🤖 附带每日定时的 GitHub Actions 工作流，自动归档历史榜单并推送 Slack

## 快速开始

```bash
# 今日热门（控制台输出）
python3 trending.py

# 本周 Rust 项目，取前 10 个，输出 Markdown
python3 trending.py --since weekly --language rust --limit 10 --format markdown

# 生成 JSON 供其它程序消费
python3 trending.py --format json -o today.json

# 推送到 Slack（前 15 个）
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/XXX/YYY/ZZZ"
python3 trending.py --since daily --slack --slack-limit 15
```

## 命令行参数

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `--since` | 时间范围：`daily` / `weekly` / `monthly` | `daily` |
| `--language`, `-l` | 按编程语言过滤，如 `python`、`rust` | 全部 |
| `--spoken-language` | 按自然语言过滤，如 `zh`、`en` | 全部 |
| `--limit`, `-n` | 只显示前 N 个 | 全部 |
| `--format`, `-f` | 输出格式：`console` / `markdown` / `json` | `console` |
| `--output`, `-o` | 写入文件而非标准输出 | 标准输出 |
| `--slack [URL]` | 推送到 Slack Webhook；省略 URL 时读环境变量 `SLACK_WEBHOOK_URL` | 关闭 |
| `--slack-limit` | 推送到 Slack 时最多展示的项目数 | 15 |

## 推送到 Slack

1. 在 Slack 中创建一个 [Incoming Webhook](https://api.slack.com/messaging/webhooks)，
   得到形如 `https://hooks.slack.com/services/XXX/YYY/ZZZ` 的地址。
2. 命令行手动推送：

   ```bash
   python3 trending.py --slack "https://hooks.slack.com/services/XXX/YYY/ZZZ"
   # 或用环境变量，避免把地址写进命令历史
   export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/XXX/YYY/ZZZ"
   python3 trending.py --slack
   ```

3. **每天自动推送**：在仓库 **Settings → Secrets and variables → Actions** 里
   新增一个名为 `SLACK_WEBHOOK_URL` 的 Secret，值为你的 Webhook 地址。
   之后每日工作流就会在归档的同时把榜单推送到 Slack（未配置该 Secret 时会自动跳过）。

## 作为库调用

```python
import trending

for r in trending.get_trending(since="daily", language="python", limit=5):
    print(r.rank, r.full_name, r.stars, f"+{r.stars_period}", r.language)
```

`get_trending()` 返回 `Repo` 数据类列表，字段包含
`owner / name / url / description / language / stars / forks / stars_period / built_by`。

## 每日自动归档

仓库内置了工作流 [`.github/workflows/daily-trending.yml`](.github/workflows/daily-trending.yml)：

- 每天 UTC 01:00（北京时间 09:00）自动运行
- 把当天榜单写入 `reports/YYYY-MM-DD.md`，并更新 `reports/latest.md`
- 有变化时自动提交回仓库

也可在 Actions 页面手动触发（`workflow_dispatch`），并选择时间范围。

> 需要在仓库 **Settings → Actions → General → Workflow permissions** 中启用
> “Read and write permissions”，工作流才能提交归档。

## 实现说明

GitHub 没有官方的 trending API，本工具抓取并解析 `https://github.com/trending`
页面。页面结构若有调整，只需更新 `trending.py` 中 `parse()` 的正则即可。

## 测试

```bash
python3 -m unittest test_trending -v
```

## 许可证

MIT
