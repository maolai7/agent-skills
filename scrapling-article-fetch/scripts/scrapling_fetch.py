#!/usr/bin/env python3
import json
import re
import sys
from urllib.parse import urlparse

import html2text
from scrapling.fetchers import Fetcher

DEFAULT_SELECTORS = [
    "article",
    "main",
    ".post-content",
    '[class*="body"]',
]

WECHAT_SELECTORS = [
    "#js_content",
    ".rich_media_content",
    ".rich_media_area_primary",
]

WECHAT_TITLE_SELECTORS = [
    "#activity-name",
    ".rich_media_title",
    "h1",
]

WECHAT_COVER_SELECTORS = [
    '.rich_media_thumb[style*="background-image"]',
    '.rich_media_thumb',
    'meta[property="og:image"]',
]

NOISE_MARKERS = [
    "Scan with Weixin to",
    "微信扫一扫可打开此内容",
    "轻触阅读原文",
    "预览时标签不可点",
    "Got It",
    "Cancel",
    "Allow",
]


def choose_selectors(url: str):
    host = (urlparse(url).hostname or "").lower()
    if host.endswith("mp.weixin.qq.com"):
        return WECHAT_SELECTORS + DEFAULT_SELECTORS
    return DEFAULT_SELECTORS


def normalize_html_for_images(html: str) -> str:
    return re.sub(
        r'<img([^>]*?)\sdata-src="([^"]+)"([^>]*?)>',
        lambda m: f'<img{m.group(1)} src="{m.group(2)}"{m.group(3)}>',
        html,
        flags=re.IGNORECASE,
    )


def strip_tail_noise(markdown: str) -> str:
    cut_positions = [markdown.find(marker) for marker in NOISE_MARKERS if marker in markdown]
    cut_positions = [p for p in cut_positions if p >= 0]
    if cut_positions:
        markdown = markdown[: min(cut_positions)]

    while "\n\n\n" in markdown:
        markdown = markdown.replace("\n\n\n", "\n\n")

    return markdown.strip()


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def get_text(node) -> str:
    if not node:
        return ""
    for attr in ("text", "text_content", "html_content"):
        value = getattr(node, attr, None)
        if isinstance(value, str) and value.strip():
            return clean_text(value)
        if callable(value):
            try:
                out = value()
                if isinstance(out, str) and out.strip():
                    return clean_text(out)
            except Exception:
                pass
    return clean_text(str(node))


def get_attr(node, attr: str) -> str:
    if not node:
        return ""
    attributes = getattr(node, "attributes", None)
    if isinstance(attributes, dict) and attributes.get(attr):
        return attributes[attr]
    attrib = getattr(node, "attrib", None)
    if isinstance(attrib, dict) and attrib.get(attr):
        return attrib[attr]
    fn = getattr(node, "get", None)
    if callable(fn):
        try:
            value = fn(attr)
            if value:
                return value
        except Exception:
            pass
    html = getattr(node, "html_content", None) or str(node)
    m = re.search(fr'{attr}="([^"]+)"', html)
    return m.group(1) if m else ""


def extract_title(page, url: str, markdown: str = "") -> str:
    host = (urlparse(url).hostname or "").lower()
    if host.endswith("mp.weixin.qq.com"):
        for sel in WECHAT_TITLE_SELECTORS:
            nodes = page.css(sel)
            node = nodes.first if nodes else None
            text = get_text(node)
            if text:
                return text.strip()

    html = getattr(page, "html_content", None) or ""
    for pattern in [
        r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"',
        r'<meta[^>]+name="twitter:title"[^>]+content="([^"]+)"',
        r'<title>(.*?)</title>',
    ]:
        m = re.search(pattern, html, re.I | re.S)
        if m:
            text = re.sub(r"\s+", " ", m.group(1)).strip()
            if text:
                return text

    if markdown:
        for line in markdown.splitlines():
            line = line.strip()
            if not line:
                continue
            if re.match(r"!\[[^\]]*\]\(([^)]+)\)", line):
                continue
            line = re.sub(r"^>\s*", "", line)
            line = re.sub(r"^[#\s]+", "", line)
            line = re.sub(r"^\*\*(.*?)\*\*$", r"\1", line)
            if line:
                return line.strip()
    return ""


def extract_cover_url(page, url: str, markdown: str = "") -> str:
    host = (urlparse(url).hostname or "").lower()
    html = getattr(page, "html_content", None) or ""
    if host.endswith("mp.weixin.qq.com"):
        for sel in WECHAT_COVER_SELECTORS:
            nodes = page.css(sel)
            node = nodes.first if nodes else None
            if not node:
                continue
            if sel.startswith("meta"):
                content = get_attr(node, "content")
                if content:
                    return content.strip()
            style = get_attr(node, "style")
            if style:
                m = re.search(r'background-image:\s*url\([\"\']?([^\)\"\']+)', style)
                if m:
                    return m.group(1).strip()
            for attr in ("data-src", "src"):
                value = get_attr(node, attr)
                if value:
                    return value.strip()

    m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html, re.I)
    if m:
        return m.group(1).strip()

    if markdown:
        m = re.search(r'!\[[^\]]*\]\(([^)]+)\)', markdown)
        if m:
            return m.group(1).strip()
    return ""


def extract_markdown(url: str, max_chars: int = 30000) -> str:
    return extract_article(url, max_chars)["markdown"]


def extract_article(url: str, max_chars: int = 30000) -> dict:
    page = Fetcher.get(url)
    status = getattr(page, "status", None)
    if isinstance(status, int) and status >= 400:
        raise RuntimeError(f"HTTP {status} for {url}")

    chosen_html = None
    for sel in choose_selectors(url):
        nodes = page.css(sel)
        node = nodes.first if nodes else None
        if node:
            chosen_html = getattr(node, "html_content", None) or str(node)
            break

    if not chosen_html:
        chosen_html = getattr(page, "html_content", None) or ""

    chosen_html = normalize_html_for_images(chosen_html)

    parser = html2text.HTML2Text()
    parser.ignore_links = False
    parser.ignore_images = False
    parser.body_width = 0

    markdown = parser.handle(chosen_html).strip()
    markdown = strip_tail_noise(markdown)
    title = extract_title(page, url, markdown)
    cover_url = extract_cover_url(page, url, markdown)
    if cover_url and cover_url not in markdown:
        markdown = f"![]({cover_url})\n\n{markdown}".strip()
    markdown = markdown[:max_chars]

    return {
        "title": title,
        "cover_url": cover_url,
        "markdown": markdown,
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scrapling_fetch.py <url> [max_chars] [--json]", file=sys.stderr)
        return 1

    args = [a for a in sys.argv[1:] if a != "--json"]
    as_json = "--json" in sys.argv[1:]
    url = args[0]
    max_chars = int(args[1]) if len(args) > 1 else 30000

    try:
        article = extract_article(url, max_chars)
        if as_json:
            print(json.dumps(article, ensure_ascii=False))
        else:
            print(article["markdown"])
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
