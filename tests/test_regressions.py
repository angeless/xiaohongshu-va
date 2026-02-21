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

        mock_run_script.assert_has_calls(
            [call("step3_batch.py"), call("step2_analyzer.py"), call("step4_uploader.py")]
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


if __name__ == "__main__":
    unittest.main()
