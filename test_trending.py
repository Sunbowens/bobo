"""trending.py 的单元测试 (仅标准库, 用 `python3 -m unittest` 运行)。"""
import json
import unittest
from unittest import mock

import trending

FIXTURE = """
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/octocat/hello-world" data-view-component="true">
      <span class="text-normal">octocat /</span> hello-world
    </a>
  </h2>
  <p class="col-9 color-fg-muted my-1 pr-4">A tiny <em>example</em> repo &amp; friends</p>
  <div class="f6 color-fg-muted mt-2">
    <span itemprop="programmingLanguage">Python</span>
    <a href="/octocat/hello-world/stargazers" class="Link--muted">12,345</a>
    <a href="/octocat/hello-world/forks" class="Link--muted">678</a>
    <span class="d-inline-block float-sm-right">1,234 stars today</span>
  </div>
</article>
<article class="Box-row">
  <h2 class="h3 lh-condensed"><a href="/torvalds/linux">torvalds / linux</a></h2>
  <div class="f6 color-fg-muted mt-2">
    <span itemprop="programmingLanguage">C</span>
    <a href="/torvalds/linux/stargazers">180,000</a>
    <a href="/torvalds/linux/forks">50,000</a>
    <span class="d-inline-block float-sm-right">42 stars today</span>
  </div>
</article>
"""


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.repos = trending.parse(FIXTURE, "daily")

    def test_count(self):
        self.assertEqual(len(self.repos), 2)

    def test_names(self):
        self.assertEqual(self.repos[0].full_name, "octocat/hello-world")
        self.assertEqual(self.repos[1].full_name, "torvalds/linux")

    def test_numbers(self):
        r = self.repos[0]
        self.assertEqual(r.stars, 12345)
        self.assertEqual(r.forks, 678)
        self.assertEqual(r.stars_period, 1234)

    def test_language_and_description(self):
        self.assertEqual(self.repos[0].language, "Python")
        self.assertEqual(self.repos[0].description, "A tiny example repo & friends")

    def test_weekly_label(self):
        html = FIXTURE.replace("stars today", "stars this week")
        repos = trending.parse(html, "weekly")
        self.assertEqual(repos[0].stars_period, 1234)


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.repos = trending.parse(FIXTURE, "daily")

    def test_markdown_has_rows(self):
        md = trending.to_markdown(self.repos, "daily")
        self.assertIn("octocat/hello-world", md)
        self.assertIn("| 12,345 |", md)

    def test_json_roundtrip(self):
        import json

        data = json.loads(trending.to_json(self.repos))
        self.assertEqual(data[0]["owner"], "octocat")

    def test_empty_console(self):
        self.assertIn("未获取到", trending.to_console([], "daily"))


class SlackTest(unittest.TestCase):
    def setUp(self):
        self.repos = trending.parse(FIXTURE, "daily")

    def test_payload_shape(self):
        p = trending.to_slack_payload(self.repos, "daily")
        self.assertEqual(p["blocks"][0]["type"], "header")
        self.assertTrue(any(b["type"] == "section" for b in p["blocks"]))
        self.assertIn("octocat/hello-world", json.dumps(p, ensure_ascii=False))

    def test_empty_payload(self):
        p = trending.to_slack_payload([], "daily")
        self.assertIn("未获取到", json.dumps(p, ensure_ascii=False))

    def test_section_char_limit(self):
        p = trending.to_slack_payload(self.repos * 80, "daily", limit=160)
        for b in p["blocks"]:
            if b["type"] == "section":
                self.assertLessEqual(len(b["text"]["text"]), 3000)

    def test_post_ok(self):
        resp = mock.MagicMock()
        resp.read.return_value = b"ok"
        resp.__enter__.return_value = resp
        with mock.patch("urllib.request.urlopen", return_value=resp) as op:
            trending.post_to_slack("http://x/hook", {"text": "hi"})
            self.assertEqual(op.call_args[0][0].get_method(), "POST")

    def test_post_non_ok_raises(self):
        resp = mock.MagicMock()
        resp.read.return_value = b"invalid_payload"
        resp.__enter__.return_value = resp
        with mock.patch("urllib.request.urlopen", return_value=resp):
            with self.assertRaises(RuntimeError):
                trending.post_to_slack("http://x/hook", {"text": "hi"})


class CliTest(unittest.TestCase):
    def test_main_markdown(self):
        with mock.patch("trending.fetch", return_value=FIXTURE), mock.patch(
            "builtins.print"
        ):
            self.assertEqual(trending.main(["--format", "markdown"]), 0)

    def test_main_slack_missing_webhook(self):
        env = {k: v for k, v in __import__("os").environ.items()}
        env.pop("SLACK_WEBHOOK_URL", None)
        with mock.patch("trending.fetch", return_value=FIXTURE), mock.patch(
            "builtins.print"
        ), mock.patch.dict("os.environ", env, clear=True):
            self.assertEqual(trending.main(["--slack"]), 2)

    def test_main_slack_posts(self):
        with mock.patch("trending.fetch", return_value=FIXTURE), mock.patch(
            "trending.post_to_slack"
        ) as post, mock.patch("builtins.print"):
            self.assertEqual(trending.main(["--slack", "http://x/hook"]), 0)
            post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
