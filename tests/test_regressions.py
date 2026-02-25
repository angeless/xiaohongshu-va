import importlib.util
import os
import unittest
from unittest.mock import call, mock_open, patch

import step5_auto_pipeline


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_module(module_name, rel_path):
    module_path = os.path.join(ROOT_DIR, rel_path)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


extract_subtitle = load_module("extract_subtitle", "scripts/extract_subtitle.py")
extract_subtitle_funasr = load_module("extract_subtitle_funasr", "scripts/extract_subtitle_funasr.py")
login_tool = load_module("login_tool", "login_tool.py")
step1_scraper = load_module("step1_scraper", "step1_scraper.py")


class TimestampFormatRegressionTest(unittest.TestCase):
    def test_ffmpeg_seek_supports_over_59_seconds(self):
        self.assertEqual(extract_subtitle.format_ffmpeg_seek(125), "00:02:05")
        self.assertEqual(extract_subtitle_funasr.format_ffmpeg_seek(3661), "01:01:01")

    def test_srt_timestamp_format_for_long_seconds(self):
        self.assertEqual(extract_subtitle.format_timestamp(125.0), "00:02:05,000")
        self.assertEqual(extract_subtitle_funasr.format_timestamp(3723.4), "01:02:03,400")


class FailedUrlExtractRegressionTest(unittest.TestCase):
    def test_extract_failed_urls_handles_short_logs(self):
        lines = ["❌ 下载失败\n"]
        self.assertEqual(step5_auto_pipeline.extract_failed_urls_from_lines(lines), [])

    def test_extract_failed_urls_find_recent_link(self):
        lines = [
            "🔗 https://example.com/a\n",
            "日志行\n",
            "❌ 下载失败\n",
            "🔗 https://example.com/b\n",
            "❌ 本次抓取失败\n",
            "❌ 本次抓取失败\n",
        ]
        self.assertEqual(
            step5_auto_pipeline.extract_failed_urls_from_lines(lines),
            ["https://example.com/a", "https://example.com/b"],
        )


class PipelineSmokeTest(unittest.TestCase):
    @patch("step5_auto_pipeline.check_failed_downloads")
    @patch("step5_auto_pipeline.run_script")
    @patch("step5_auto_pipeline.log_message")
    @patch("step5_auto_pipeline.time.time", side_effect=[100.0, 220.0])
    @patch("step5_auto_pipeline.os.path.getsize", return_value=1)
    @patch("step5_auto_pipeline.os.path.exists", return_value=True)
    @patch("step5_auto_pipeline.open", new_callable=mock_open)
    def test_main_runs_scripts_in_order(
        self,
        _mock_open,
        _mock_exists,
        _mock_getsize,
        _mock_time,
        _mock_log,
        mock_run_script,
        mock_check_failed,
    ):
        step5_auto_pipeline.main()

        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        mock_run_script.assert_has_calls(
            [
                call(os.path.join(base, "step3_batch.py")),
                call(os.path.join(base, "step2_analyzer.py")),
                call(os.path.join(base, "step4_uploader.py")),
            ]
        )
        self.assertEqual(mock_run_script.call_count, 3)
        mock_check_failed.assert_called_once()

    @patch("step5_auto_pipeline.run_script")
    @patch("step5_auto_pipeline.log_message")
    @patch("step5_auto_pipeline.os.path.exists", return_value=False)
    @patch("step5_auto_pipeline.open", new_callable=mock_open)
    def test_main_exits_early_when_urls_missing(
        self, _mock_open, _mock_exists, _mock_log, mock_run_script
    ):
        step5_auto_pipeline.main()
        mock_run_script.assert_not_called()


class LoginFlowRegressionTest(unittest.TestCase):
    class _FakeContext:
        def __init__(self, cookies):
            self._cookies = cookies

        def cookies(self, *_args, **_kwargs):
            return self._cookies

    class _FakePage:
        def __init__(self, selector_hits=None):
            self.selector_hits = selector_hits or set()

        def query_selector(self, selector):
            return object() if selector in self.selector_hits else None

    class _WaitPage:
        def __init__(self):
            self.wait_calls = 0
            self.load_called = 0
            self.url = "https://www.xiaohongshu.com/"

        def wait_for_timeout(self, _ms):
            self.wait_calls += 1

        def wait_for_load_state(self, *_args, **_kwargs):
            self.load_called += 1

        def is_closed(self):
            return False

    def test_is_logged_in_true_when_web_session_cookie_exists(self):
        context = self._FakeContext([{"name": "web_session"}])
        page = self._FakePage()
        self.assertTrue(login_tool.is_logged_in(context, page))

    def test_wait_for_login_if_needed_can_resume_when_login_clears(self):
        page = self._WaitPage()
        context = self._FakeContext([{"name": "web_session"}])
        with patch.object(
            step1_scraper, "page_requires_login", side_effect=[True, True, False]
        ):
            ok = step1_scraper.wait_for_login_if_needed(
                page, context=context, timeout_seconds=5, poll_seconds=0
            )
        self.assertTrue(ok)
        self.assertGreaterEqual(page.wait_calls, 1)
        self.assertEqual(page.load_called, 1)

    def test_page_requires_login_false_if_has_auth_cookie(self):
        class _Page:
            url = "https://www.xiaohongshu.com/explore/abc"

            def is_closed(self):
                return False

            def query_selector(self, *_args, **_kwargs):
                return None

            def content(self):
                return "扫码登录"

        context = self._FakeContext([{"name": "web_session"}])
        self.assertFalse(step1_scraper.page_requires_login(_Page(), context=context))

    def test_wait_for_login_timeout_when_no_cookie_under_strict_mode(self):
        page = self._WaitPage()
        context = self._FakeContext([])
        with patch.object(step1_scraper, "STRICT_LOGIN_REQUIRED", True), patch.object(
            step1_scraper, "page_requires_login", return_value=False
        ):
            ok = step1_scraper.wait_for_login_if_needed(
                page, context=context, timeout_seconds=0, poll_seconds=0
            )
        self.assertFalse(ok)


class ProfileModeRegressionTest(unittest.TestCase):
    def test_is_profile_url(self):
        self.assertTrue(
            step1_scraper.is_profile_url("https://www.xiaohongshu.com/user/profile/123abc")
        )
        self.assertFalse(
            step1_scraper.is_profile_url("https://www.xiaohongshu.com/explore/66cdef")
        )

    def test_extract_note_id(self):
        self.assertEqual(
            step1_scraper._extract_note_id("https://www.xiaohongshu.com/explore/66cdef"),
            "66cdef",
        )
        self.assertEqual(step1_scraper._extract_note_id(""), "unknown")

    @patch("step1_scraper.subprocess.run")
    @patch("step1_scraper.os.path.exists", return_value=True)
    def test_download_video_with_ytdlp_prefers_mp4_path(self, mock_exists, mock_run):
        class _Proc:
            returncode = 0
            stderr = ""
            stdout = ""

        mock_run.return_value = _Proc()
        out = step1_scraper.download_video_with_ytdlp("https://example.com/note", 123)
        self.assertTrue(out.endswith("workspace_data/video_123.mp4"))


if __name__ == "__main__":
    unittest.main()
