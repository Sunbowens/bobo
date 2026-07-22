#!/usr/bin/env python3
"""观测每日 GitHub 热门项目 / Observe daily trending GitHub projects.

零依赖（仅需 Python 3 标准库），抓取并解析 https://github.com/trending，
输出为控制台表格、Markdown 或 JSON。

用法示例:
    python3 trending.py                          # 今日全部语言, 控制台输出
    python3 trending.py --since weekly           # 本周
    python3 trending.py --language python         # 仅 Python
    python3 trending.py --format markdown         # Markdown
    python3 trending.py --format json --limit 10  # JSON, 前 10 个
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from html import unescape
from typing import Iterable

TRENDING_URL = "https://github.com/trending"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
SINCE_LABEL = {"daily": "today", "weekly": "this week", "monthly": "this month"}


@dataclass
class Repo:
    """一个热门仓库的信息。"""

    rank: int
    owner: str
    name: str
    url: str
    description: str = ""
    language: str = ""
    stars: int = 0
    forks: int = 0
    stars_period: int = 0  # 该时间段内新增的 star 数
    built_by: list[str] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


def fetch(
    since: str = "daily",
    language: str | None = None,
    spoken_language: str | None = None,
    timeout: int = 20,
) -> str:
    """抓取 GitHub trending 页面的 HTML。"""
    params = [f"since={since}"]
    if spoken_language:
        params.append(f"spoken_language_code={spoken_language}")
    path = f"/{language}" if language else ""
    url = f"{TRENDING_URL}{path}?{'&'.join(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def _clean(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text)).strip()


def _to_int(text: str) -> int:
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else 0


def parse(html: str, since: str = "daily") -> list[Repo]:
    """从 trending 页面 HTML 中解析出仓库列表。"""
    repos: list[Repo] = []
    # 每个仓库都在一个 <article class="Box-row"> ... </article> 块内。
    blocks = re.split(r'<article class="Box-row">', html)[1:]
    period_word = SINCE_LABEL.get(since, "today")

    for i, block in enumerate(blocks, start=1):
        block = block.split("</article>", 1)[0]

        m = re.search(r'<h2[^>]*>\s*<a href="/([^"/]+)/([^"?]+)"', block)
        if not m:
            continue
        owner, name = m.group(1), m.group(2).rstrip("/")

        repo = Repo(
            rank=i,
            owner=owner,
            name=name,
            url=f"https://github.com/{owner}/{name}",
        )

        desc = re.search(r'<p class="col-9[^"]*">(.*?)</p>', block, re.S)
        if desc:
            repo.description = _clean(re.sub(r"<[^>]+>", "", desc.group(1)))

        lang = re.search(r'itemprop="programmingLanguage">([^<]+)<', block)
        if lang:
            repo.language = _clean(lang.group(1))

        stars = re.search(
            rf'href="/{owner}/{name}/stargazers"[^>]*>(.*?)</a>', block, re.S
        )
        if stars:
            repo.stars = _to_int(stars.group(1))

        forks = re.search(
            rf'href="/{owner}/{name}/(?:forks|network/members)"[^>]*>(.*?)</a>',
            block,
            re.S,
        )
        if forks:
            repo.forks = _to_int(forks.group(1))

        period = re.search(rf"([\d,]+)\s+stars?\s+{re.escape(period_word)}", block)
        if period:
            repo.stars_period = _to_int(period.group(1))

        for who in re.findall(r'Built by.*?</span>', block, re.S):
            repo.built_by = re.findall(r'href="/([^"/]+)"', who)

        repos.append(repo)

    return repos


def get_trending(
    since: str = "daily",
    language: str | None = None,
    spoken_language: str | None = None,
    limit: int | None = None,
) -> list[Repo]:
    """抓取并解析，返回热门仓库列表。"""
    repos = parse(fetch(since, language, spoken_language), since)
    return repos[:limit] if limit else repos


# --------------------------------------------------------------------------- #
# 输出格式
# --------------------------------------------------------------------------- #
def _period_header(since: str) -> str:
    return {"daily": "今日新增", "weekly": "本周新增", "monthly": "本月新增"}.get(
        since, "新增"
    )


def to_console(repos: Iterable[Repo], since: str = "daily") -> str:
    repos = list(repos)
    if not repos:
        return "未获取到任何热门项目。"
    lines = []
    for r in repos:
        star_note = f"+{r.stars_period}" if r.stars_period else ""
        lines.append(
            f"{r.rank:>2}. {r.full_name}  "
            f"[⭐{r.stars:,} {star_note}]"
            + (f"  <{r.language}>" if r.language else "")
        )
        if r.description:
            lines.append(f"    {r.description}")
    return "\n".join(lines)


def to_markdown(repos: Iterable[Repo], since: str = "daily", title: str | None = None) -> str:
    repos = list(repos)
    date = _dt.date.today().isoformat()
    header = _period_header(since)
    out = [
        title or f"# GitHub 热门项目 · {date}",
        "",
        f"> 时间范围: **{since}** · 生成时间: {date}",
        "",
        f"| # | 项目 | 语言 | ⭐ 总数 | {header} | 描述 |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for r in repos:
        desc = r.description.replace("|", "\\|")
        period = f"+{r.stars_period:,}" if r.stars_period else "-"
        out.append(
            f"| {r.rank} | [{r.full_name}]({r.url}) | {r.language or '-'} "
            f"| {r.stars:,} | {period} | {desc} |"
        )
    out.append("")
    return "\n".join(out)


def to_json(repos: Iterable[Repo]) -> str:
    return json.dumps([asdict(r) for r in repos], ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------- #
# Slack
# --------------------------------------------------------------------------- #
def to_slack_payload(
    repos: Iterable[Repo], since: str = "daily", limit: int = 15
) -> dict:
    """构造 Slack Incoming Webhook 的消息 (Block Kit)。"""
    repos = list(repos)[:limit]
    date = _dt.date.today().isoformat()
    title = f":fire: GitHub 热门项目 · {since} · {date}"
    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": title, "emoji": True}}
    ]
    if not repos:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "_未获取到任何热门项目。_"},
            }
        )
        return {"text": title, "blocks": blocks}

    # 每行一个仓库；Slack 单个 section 上限 3000 字符，按需分块。
    lines, chunks, size = [], [], 0
    for r in repos:
        star = f"  ·  +{r.stars_period:,} ⭐" if r.stars_period else ""
        lang = f"  ·  `{r.language}`" if r.language else ""
        desc = f"\n{r.description}" if r.description else ""
        line = (
            f"*{r.rank}.* <{r.url}|{r.full_name}>{lang}"
            f"  ·  ⭐ {r.stars:,}{star}{desc}"
        )
        if size + len(line) > 2800 and lines:
            chunks.append("\n\n".join(lines))
            lines, size = [], 0
        lines.append(line)
        size += len(line)
    if lines:
        chunks.append("\n\n".join(lines))

    for chunk in chunks:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": chunk}})
    blocks.append(
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"来源 https://github.com/trending?since={since}"}
            ],
        }
    )
    return {"text": title, "blocks": blocks}


def post_to_slack(webhook_url: str, payload: dict, timeout: int = 20) -> None:
    """把消息 POST 到 Slack Incoming Webhook。失败时抛出异常。"""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        body = resp.read().decode("utf-8", errors="replace")
        if body.strip() != "ok":
            raise RuntimeError(f"Slack 返回异常: {body!r}")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="观测每日 GitHub 热门项目 (Observe trending GitHub projects)."
    )
    p.add_argument(
        "--since",
        choices=["daily", "weekly", "monthly"],
        default="daily",
        help="时间范围 (默认: daily)",
    )
    p.add_argument("--language", "-l", help="按编程语言过滤, 如 python, rust")
    p.add_argument(
        "--spoken-language", help="按自然语言过滤, 如 zh, en"
    )
    p.add_argument("--limit", "-n", type=int, help="只显示前 N 个")
    p.add_argument(
        "--format",
        "-f",
        choices=["console", "markdown", "json"],
        default="console",
        help="输出格式 (默认: console)",
    )
    p.add_argument("--output", "-o", help="写入文件, 而非标准输出")
    p.add_argument(
        "--slack",
        nargs="?",
        const="",
        metavar="WEBHOOK_URL",
        help="推送到 Slack Incoming Webhook；不给值时读取环境变量 SLACK_WEBHOOK_URL",
    )
    p.add_argument(
        "--slack-limit",
        type=int,
        default=15,
        help="推送到 Slack 时最多展示的项目数 (默认: 15)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        repos = get_trending(
            since=args.since,
            language=args.language,
            spoken_language=args.spoken_language,
            limit=args.limit,
        )
    except urllib.error.URLError as exc:  # 网络错误
        print(f"抓取失败: {exc}", file=sys.stderr)
        return 1

    # 推送到 Slack（可与其它输出并存）。
    if args.slack is not None:
        webhook = args.slack or os.environ.get("SLACK_WEBHOOK_URL", "")
        if not webhook:
            print(
                "未提供 Slack Webhook：请用 --slack <URL> 或设置环境变量 SLACK_WEBHOOK_URL",
                file=sys.stderr,
            )
            return 2
        payload = to_slack_payload(repos, args.since, args.slack_limit)
        try:
            post_to_slack(webhook, payload)
        except (urllib.error.URLError, RuntimeError) as exc:
            print(f"推送 Slack 失败: {exc}", file=sys.stderr)
            return 1
        print(f"已推送 {min(len(repos), args.slack_limit)} 个项目到 Slack", file=sys.stderr)
        if not args.output and args.format == "console":
            return 0  # 仅推送 Slack，不再打印到控制台

    if args.format == "markdown":
        text = to_markdown(repos, args.since)
    elif args.format == "json":
        text = to_json(repos)
    else:
        text = to_console(repos, args.since)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"已写入 {args.output} ({len(repos)} 个项目)", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
