"""Tests for the Python fetch entrypoint wrapper."""

from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from fetch_article import emit_completed_process, resolve_output_root, save_article_outputs


class EmitCompletedProcessTests(unittest.TestCase):
    def test_success_discards_info_stderr(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["python", "scrapling_fetch.py"],
            returncode=0,
            stdout="ok-json",
            stderr="[2026-06-21 15:40:55] INFO: Fetched (200) <GET https://example.com>\n",
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        code = emit_completed_process(completed, stdout=stdout, stderr=stderr)

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), "ok-json")
        self.assertEqual(stderr.getvalue(), "")

    def test_failure_keeps_stderr(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["python", "scrapling_fetch.py"],
            returncode=2,
            stdout="",
            stderr="[ERROR] boom\n",
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        code = emit_completed_process(completed, stdout=stdout, stderr=stderr)

        self.assertEqual(code, 2)
        self.assertEqual(stderr.getvalue(), "[ERROR] boom\n")


class OutputPersistenceTests(unittest.TestCase):
    def test_resolves_project_temp_root_from_nested_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "WorkBuddyGO"
            nested = workspace / "docs" / "demo"
            (workspace / ".git").mkdir(parents=True)
            nested.mkdir(parents=True)

            resolved = resolve_output_root(nested)

            self.assertEqual(resolved, workspace / "Temp")

    def test_falls_back_to_system_temp_outside_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = Path(tmpdir) / "somewhere"
            nested.mkdir(parents=True)

            resolved = resolve_output_root(nested)

            self.assertEqual(resolved, Path(tempfile.gettempdir()))

    def test_save_article_outputs_uses_project_style_archive_layout(self) -> None:
        article = {
            "title": "测试文章",
            "cover_url": "https://example.com/cover.jpg",
            "markdown": "# 正文\n\n这是一段测试内容。",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir)

            saved = save_article_outputs(
                article,
                "https://mp.weixin.qq.com/s/demo",
                output_root=output_root,
                now=datetime(2026, 6, 21, 9, 8, 7),
            )

            day_dir = output_root / "scrapling-article-fetch" / "2026" / "06" / "2026-06-21"
            self.assertEqual(saved["day_dir"], day_dir)
            self.assertEqual(saved["json_path"], day_dir / "测试文章.json")
            self.assertEqual(saved["md_path"], day_dir / "测试文章.md")
            self.assertTrue((day_dir / "测试文章.json").exists())
            self.assertTrue((day_dir / "测试文章.md").exists())
            self.assertFalse((day_dir / "runs").exists())

            latest_json = json.loads((day_dir / "测试文章.json").read_text(encoding="utf-8"))
            self.assertEqual(latest_json["title"], "测试文章")
            self.assertEqual(latest_json["source_url"], "https://mp.weixin.qq.com/s/demo")

            latest_markdown = (day_dir / "测试文章.md").read_text(encoding="utf-8")
            self.assertIn("测试文章", latest_markdown)
            self.assertIn("原文链接：https://mp.weixin.qq.com/s/demo", latest_markdown)
            self.assertIn("这是一段测试内容。", latest_markdown)


if __name__ == "__main__":
    unittest.main()
