#!/usr/bin/env python3
"""Run the article fetcher with a single Python entrypoint across platforms."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

from io_utils import configure_utf8_stdio

SKILL_NAME = "scrapling-article-fetch"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch article content as markdown or JSON.")
    parser.add_argument("url", help="Article URL to fetch.")
    parser.add_argument("max_chars", nargs="?", type=int, default=30000, help="Maximum characters to keep.")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Print JSON instead of markdown.")
    parser.add_argument("--output-root", help="Directory that contains skill output folders.")
    parser.add_argument("--no-save", action="store_true", help="Do not persist fetched content to local files.")
    return parser


def build_command(script_path: Path, url: str, max_chars: int, as_json: bool) -> list[str]:
    base_args = [str(script_path), url, str(max_chars)]
    if as_json:
        base_args.append("--json")

    if shutil.which("uv"):
        return [
            "uv",
            "run",
            "--with",
            "scrapling[fetchers]",
            "--with",
            "html2text",
            "python",
            *base_args,
        ]

    return [sys.executable, *base_args]


def emit_completed_process(
    completed: subprocess.CompletedProcess[str],
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    out_stream = stdout or sys.stdout
    err_stream = stderr or sys.stderr

    if completed.stdout:
        out_stream.write(completed.stdout)

    if completed.returncode != 0 and completed.stderr:
        err_stream.write(completed.stderr)

    return completed.returncode


def execute_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def find_project_root(start_dir: Path) -> Path | None:
    current = start_dir.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def resolve_output_root(start_dir: Path) -> Path:
    project_root = find_project_root(start_dir)
    if project_root is not None:
        return project_root / "Temp"
    return Path(tempfile.gettempdir())


def build_markdown_document(article: dict[str, Any], source_url: str) -> str:
    title = str(article.get("title") or "").strip() or "未命名文章"
    cover_url = str(article.get("cover_url") or "").strip()
    markdown = str(article.get("markdown") or "").strip()

    sections = [f"# {title}", "", f"原文链接：{source_url}"]
    if cover_url:
        sections.extend(["", f"封面图：{cover_url}"])
    if markdown:
        sections.extend(["", markdown])
    return "\n".join(sections).strip() + "\n"


def sanitize_filename(title: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", title).strip().rstrip(". ")
    return cleaned or "untitled-article"


def save_article_outputs(
    article: dict[str, Any],
    source_url: str,
    *,
    output_root: Path,
    now: datetime | None = None,
) -> dict[str, Path]:
    timestamp = now or datetime.now()
    day_dir = output_root / SKILL_NAME / timestamp.strftime("%Y") / timestamp.strftime("%m") / timestamp.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)

    article_title = str(article.get("title") or "").strip() or "未命名文章"
    payload = {
        "skill_name": SKILL_NAME,
        "source_url": source_url,
        "fetched_at": timestamp.isoformat(timespec="seconds"),
        "title": article_title,
        "cover_url": article.get("cover_url", ""),
        "markdown": article.get("markdown", ""),
    }
    markdown_doc = build_markdown_document(article, source_url)
    file_stem = sanitize_filename(article_title)

    json_path = day_dir / f"{file_stem}.json"
    md_path = day_dir / f"{file_stem}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(markdown_doc, encoding="utf-8")

    return {
        "day_dir": day_dir,
        "json_path": json_path,
        "md_path": md_path,
    }


def print_article(article: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        sys.stdout.write(json.dumps(article, ensure_ascii=False))
    else:
        sys.stdout.write(str(article.get("markdown") or ""))


def main() -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args()
    script_path = Path(__file__).resolve().with_name("scrapling_fetch.py")
    command = build_command(script_path, args.url, args.max_chars, True)
    completed = execute_command(command)

    if completed.returncode != 0:
        return emit_completed_process(completed)

    try:
        article = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"[ERROR] Invalid JSON from scrapling_fetch.py: {exc}\n")
        return 3

    if not args.no_save:
        output_root = (
            Path(args.output_root).resolve()
            if args.output_root
            else resolve_output_root(Path.cwd())
        )
        saved = save_article_outputs(article, args.url, output_root=output_root)
        sys.stderr.write(f"[saved] {saved['md_path']}\n")

    print_article(article, as_json=args.as_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
