#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def render_reply(title: str, src_url: str, markdown: str) -> str:
    body = markdown.strip()
    return (
        "```markdown\n"
        f"# {title}\n\n"
        f"原文链接：{src_url}\n\n"
        f"{body}\n"
        "```"
    )


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: render_markdown_reply.py <title> <src_url> <markdown_file>", file=sys.stderr)
        return 2
    title, src_url, markdown_file = sys.argv[1:4]
    markdown = Path(markdown_file).read_text(encoding="utf-8")
    print(render_reply(title, src_url, markdown))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
