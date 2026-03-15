#!/usr/bin/env python3
import json
import mimetypes
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

FEISHU_AUTH_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
FEISHU_DOC_CREATE_URL = "https://open.feishu.cn/open-apis/docx/v1/documents"
OPENCLAW_CONFIG = Path("/home/lenovo/.openclaw/openclaw.json")


def resolve_current_agent_account() -> tuple[str, str, str]:
    cfg = json.loads(OPENCLAW_CONFIG.read_text(encoding="utf-8"))
    cwd = Path.cwd().resolve()

    agent_id = os.environ.get("OPENCLAW_AGENT_ID") or os.environ.get("AGENT_ID")
    if not agent_id:
        for agent in cfg.get("agents", {}).get("list", []):
            workspace = agent.get("workspace")
            if workspace and Path(workspace).resolve() == cwd:
                agent_id = agent.get("id")
                break

    if not agent_id:
        raise RuntimeError("cannot resolve current agent id from env or cwd")

    account = cfg.get("channels", {}).get("feishu", {}).get("accounts", {}).get(agent_id)
    if not account:
        raise RuntimeError(f"cannot find feishu account for current agent: {agent_id}")

    app_id = account.get("appId")
    app_secret = account.get("appSecret")
    if not app_id or not app_secret:
        raise RuntimeError(f"feishu app credentials missing for current agent: {agent_id}")

    return agent_id, app_id, app_secret


def get_token(app_id: str, app_secret: str) -> str:
    r = requests.post(FEISHU_AUTH_URL, json={"app_id": app_id, "app_secret": app_secret}, timeout=30)
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError(f"token failed: {j}")
    return j["tenant_access_token"]


def create_doc(token: str, title: str) -> str:
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(FEISHU_DOC_CREATE_URL, headers=h, json={"title": title}, timeout=30)
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError(f"create doc failed: {j}")
    return j["data"]["document"]["document_id"]


def clear_doc(token: str, doc_id: str) -> None:
    h = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks", headers=h, timeout=30)
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError(f"list blocks failed: {j}")
    items = j.get("data", {}).get("items", [])
    child_ids = [b["block_id"] for b in items if b.get("parent_id") == doc_id and b.get("block_type") != 1]
    if not child_ids:
        return
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.delete(
        f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children/batch_delete",
        headers=h,
        json={"start_index": 0, "end_index": len(child_ids)},
        timeout=30,
    )
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError(f"clear doc failed: {j}")


def add_blocks(token: str, doc_id: str, blocks: list[dict]) -> list[dict]:
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    out = []
    for i in range(0, len(blocks), 20):
        batch = blocks[i:i + 20]
        r = requests.post(
            f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
            headers=h,
            json={"children": batch},
            timeout=30,
        )
        j = r.json()
        if j.get("code") != 0:
            raise RuntimeError(f"add blocks failed: {j}")
        out.extend(j["data"].get("children", []))
    return out


def create_empty_image_block(token: str, doc_id: str) -> str:
    blocks = add_blocks(token, doc_id, [{"block_type": 27, "image": {}}])
    return [b for b in blocks if b.get("block_type") == 27][0]["block_id"]


def upload_image(token: str, doc_id: str, block_id: str, image_url: str) -> str:
    img = requests.get(image_url, timeout=60)
    img.raise_for_status()
    parsed = urlparse(image_url)
    filename = Path(parsed.path).name or "image"
    content_type = img.headers.get("Content-Type") or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    data = {
        "file_name": filename,
        "parent_type": "docx_image",
        "parent_node": block_id,
        "size": str(len(img.content)),
        "extra": json.dumps({"drive_route_token": doc_id}),
    }
    files = {"file": (filename, img.content, content_type)}
    r = requests.post(
        "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all",
        headers={"Authorization": f"Bearer {token}"},
        data=data,
        files=files,
        timeout=120,
    )
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError(f"upload image failed: {j}")
    return j["data"]["file_token"]


def patch_image(token: str, doc_id: str, block_id: str, file_token: str) -> None:
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.patch(
        f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{block_id}",
        headers=h,
        json={"replace_image": {"token": file_token}},
        timeout=30,
    )
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError(f"patch image failed: {j}")


def grant_edit_permission(token: str, doc_id: str, user_open_id: str) -> None:
    if not user_open_id:
        return
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(
        f"https://open.feishu.cn/open-apis/drive/v1/permissions/{doc_id}/members",
        headers=h,
        params={"type": "docx", "need_notification": "false"},
        json={"member_type": "openid", "member_id": user_open_id, "perm": "edit"},
        timeout=30,
    )
    j = r.json()
    if j.get("code") != 0 and j.get("msg") not in {"success", "Success"}:
        raise RuntimeError(f"grant permission failed: {j}")


def _inline_elements(text: str, *, bold: bool = False) -> list[dict]:
    parts = re.split(r"(`[^`]+`)", text)
    elements = []
    for part in parts:
        if not part:
            continue
        if part.startswith("`") and part.endswith("`") and len(part) >= 3:
            style = {"inline_code": True}
            if bold:
                style["bold"] = True
            elements.append({"text_run": {"content": part[1:-1], "text_element_style": style}})
        else:
            if bold:
                elements.append({"text_run": {"content": part, "text_element_style": {"bold": True}}})
            else:
                elements.append({"text_run": {"content": part}})
    return elements


def rich_elements(text: str) -> list[dict]:
    text = text[:2000]
    parts = re.split(r"(\*\*.*?\*\*)", text)
    elements = []
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) >= 4:
            elements.extend(_inline_elements(part[2:-2], bold=True))
        else:
            elements.extend(_inline_elements(part, bold=False))
    return elements or [{"text_run": {"content": text}}]


def text_block(text: str) -> dict:
    return {"block_type": 2, "text": {"elements": rich_elements(text)}}


def bullet_block(text: str) -> dict:
    return {"block_type": 12, "bullet": {"elements": rich_elements(text)}}


def ordered_block(text: str) -> dict:
    return {"block_type": 13, "ordered": {"elements": rich_elements(text)}}


def divider_block() -> dict:
    return {"block_type": 22, "divider": {}}


def code_block(text: str) -> dict:
    return {"block_type": 14, "code": {"elements": [{"text_run": {"content": text[:2000]}}]}}


def h1_block(text: str) -> dict:
    return {"block_type": 3, "heading1": {"elements": [{"text_run": {"content": text[:2000]}}]}}


def h2_block(text: str) -> dict:
    return {"block_type": 4, "heading2": {"elements": [{"text_run": {"content": text[:2000]}}]}}


def h3_block(text: str) -> dict:
    return {"block_type": 5, "heading3": {"elements": [{"text_run": {"content": text[:2000]}}]}}


def h4_block(text: str) -> dict:
    return {"block_type": 6, "heading4": {"elements": [{"text_run": {"content": text[:2000]}}]}}


def h5_block(text: str) -> dict:
    return {"block_type": 7, "heading5": {"elements": [{"text_run": {"content": text[:2000]}}]}}


def h6_block(text: str) -> dict:
    return {"block_type": 8, "heading6": {"elements": [{"text_run": {"content": text[:2000]}}]}}


def resolve_doc_title(title_or_meta: str, markdown: str) -> str:
    raw = (title_or_meta or "").strip()
    if raw:
        meta_path = Path(raw)
        if meta_path.suffix.lower() == ".json" and meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                meta_title = (meta.get("title") or "").strip()
                if meta_title:
                    return meta_title
            except Exception:
                pass
        return raw.replace("抓取 - ", "").strip()

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"!\[[^\]]*\]\(([^)]+)\)", line):
            continue
        if line.startswith("# "):
            return line[2:].strip()
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"!\[[^\]]*\]\(([^)]+)\)", line):
            continue
        line = re.sub(r"^#+\s*", "", line)
        line = re.sub(r"^>\s*", "", line)
        line = re.sub(r"^[-*•]\s+", "", line)
        line = re.sub(r"^\d+\.\s+", "", line)
        line = re.sub(r"^\*\*(.*?)\*\*$", r"\1", line)
        if line:
            return line.strip()
    raise RuntimeError("cannot resolve document title")


def parse_markdown(md: str):
    items = []
    lines = md.splitlines()
    ordered_re = re.compile(r"^(\d+)\.\s+(.*)$")
    bullet_re = re.compile(r"^[-*•]\s+(.*)$")

    def normalize_inline(s: str) -> str:
        return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1（\2）", s.strip())

    def normalize_heading_text(s: str) -> str:
        s = normalize_inline(s)
        if s.startswith("**") and s.endswith("**") and len(s) >= 4:
            s = s[2:-2].strip()
        return s

    def is_block_boundary(s: str) -> bool:
        s = s.strip()
        return (
            not s
            or s == "**"
            or s in {"* * *", "***", "---", "___"}
            or s.startswith("# ")
            or s.startswith("## ")
            or s.startswith("### ")
            or s.startswith("#### ")
            or s.startswith("##### ")
            or s.startswith("###### ")
            or re.match(r"!\[[^\]]*\]\(([^)]+)\)", s) is not None
            or ordered_re.match(s) is not None
            or bullet_re.match(s) is not None
            or re.match(r"^( {4}|\t)", s) is not None
        )

    i = 0
    pending_blank = False
    prev_kind = None
    preserve_blank_lines = False
    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        if re.match(r"^( {4}|\t)", raw):
            code_lines = [raw[4:] if raw.startswith('    ') else raw.lstrip('\t')]
            j = i + 1
            while j < len(lines):
                nxt_raw = lines[j]
                if re.match(r"^( {4}|\t)", nxt_raw):
                    code_lines.append(nxt_raw[4:] if nxt_raw.startswith('    ') else nxt_raw.lstrip('\t'))
                    j += 1
                    continue
                break
            code_text = "\n".join(code_lines).strip()
            if code_text:
                if preserve_blank_lines and items and items[-1][0] != 'blank' and pending_blank and prev_kind in {'text', 'image'}:
                    items.append(("blank", ""))
                items.append(("code", code_text))
                prev_kind = 'code'
                pending_blank = False
            i = j
            continue
        if line in {"* * *", "***", "---", "___"}:
            if preserve_blank_lines and items and items[-1][0] != 'blank' and pending_blank and prev_kind in {'text', 'image'}:
                items.append(("blank", ""))
            items.append(("divider", ""))
            prev_kind = 'divider'
            pending_blank = False
            i += 1
            continue
        if not line or line == "**":
            pending_blank = True
            i += 1
            continue
        m = re.match(r"!\[[^\]]*\]\(([^)]+)\)", line)
        if m:
            if preserve_blank_lines and items and items[-1][0] != 'blank' and pending_blank and prev_kind in {'text', 'image'}:
                items.append(("blank", ""))
            items.append(("image", m.group(1)))
            prev_kind = 'image'
            pending_blank = False
            i += 1
            continue
        if line.startswith("###### "):
            items.append(("h6", normalize_heading_text(line[7:])))
            prev_kind = 'h6'
            pending_blank = False
            i += 1
            continue
        if line.startswith("##### "):
            items.append(("h5", normalize_heading_text(line[6:])))
            prev_kind = 'h5'
            pending_blank = False
            i += 1
            continue
        if line.startswith("#### "):
            items.append(("h4", normalize_heading_text(line[5:])))
            prev_kind = 'h4'
            pending_blank = False
            i += 1
            continue
        if line.startswith("### "):
            items.append(("h3", normalize_heading_text(line[4:])))
            prev_kind = 'h3'
            pending_blank = False
            i += 1
            continue
        if line.startswith("## "):
            items.append(("h2", normalize_heading_text(line[3:])))
            prev_kind = 'h2'
            pending_blank = False
            i += 1
            continue
        if line.startswith("# "):
            items.append(("h1", normalize_heading_text(line[2:])))
            prev_kind = 'h1'
            pending_blank = False
            i += 1
            continue
        om = ordered_re.match(line)
        if om:
            n = om.group(1)
            text = om.group(2).strip()
            if text == f"{n}.":
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines):
                    items.append(("ordered", normalize_inline(lines[j])))
                    prev_kind = 'ordered'
                    pending_blank = False
                    i = j + 1
                    continue
            elif text:
                items.append(("ordered", normalize_inline(text)))
                prev_kind = 'ordered'
                pending_blank = False
                i += 1
                continue
        bm = bullet_re.match(line)
        if bm:
            text = bm.group(1).strip()
            if text in {"", "•", "-", "*"} and i + 1 < len(lines):
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines):
                    text = lines[j].strip()
                    i = j
            text = normalize_inline(text)
            if text and text not in {"•", "-", "*"}:
                items.append(("bullet", text))
                prev_kind = 'bullet'
                pending_blank = False
            i += 1
            continue

        para = [normalize_inline(line)]
        j = i + 1
        while j < len(lines):
            nxt = lines[j]
            if is_block_boundary(nxt):
                break
            para.append(normalize_inline(nxt))
            j += 1
        text = " ".join([p for p in para if p]).strip()
        if text:
            if preserve_blank_lines and items and items[-1][0] != 'blank' and pending_blank and prev_kind in {'text', 'image'}:
                items.append(("blank", ""))
            items.append(("text", text))
            prev_kind = 'text'
            pending_blank = False
        i = j
    return items


def main():
    if len(sys.argv) not in {4, 5, 6}:
        raise SystemExit("usage: md_to_feishu_doc.py <title_or_meta_json> <src_url> <markdown_file> [doc_id] [user_open_id]")
    title_or_meta, src_url, markdown_file = sys.argv[1:4]
    existing_doc_id = sys.argv[4] if len(sys.argv) >= 5 else None
    user_open_id = sys.argv[5] if len(sys.argv) >= 6 else ""
    md = Path(markdown_file).read_text(encoding="utf-8")
    title = resolve_doc_title(title_or_meta, md)
    _agent_id, app_id, app_secret = resolve_current_agent_account()
    doc_title = title if title.startswith("抓取 - ") else f"抓取 - {title}"
    token = get_token(app_id, app_secret)
    doc_id = existing_doc_id or create_doc(token, doc_title)
    if existing_doc_id:
        clear_doc(token, doc_id)

    doc_title = title if title.startswith("抓取 - ") else f"抓取 - {title}"

    preface = [
        ("h1", doc_title.replace("抓取 - ", "")),
        ("text", f"原文链接：{src_url}"),
        ("divider", ""),
    ]
    items = preface + parse_markdown(md)

    pending = []
    for kind, value in items:
        if kind == "h1":
            pending.append(h1_block(value))
        elif kind == "h2":
            pending.append(h2_block(value))
        elif kind == "h3":
            pending.append(h3_block(value))
        elif kind == "h4":
            pending.append(h4_block(value))
        elif kind == "h5":
            pending.append(h5_block(value))
        elif kind == "h6":
            pending.append(h6_block(value))
        elif kind == "text":
            pending.append(text_block(value))
        elif kind == "bullet":
            pending.append(bullet_block(value))
        elif kind == "ordered":
            pending.append(ordered_block(value))
        elif kind == "code":
            pending.append(code_block(value))
        elif kind == "divider":
            pending.append(divider_block())
        elif kind == "blank":
            pending.append(text_block(""))
        elif kind == "image":
            if pending:
                add_blocks(token, doc_id, pending)
                pending = []
            block_id = create_empty_image_block(token, doc_id)
            try:
                file_token = upload_image(token, doc_id, block_id, value)
                patch_image(token, doc_id, block_id, file_token)
            except Exception:
                add_blocks(token, doc_id, [text_block(f"图片原链接：{value}")])

    if pending:
        add_blocks(token, doc_id, pending)

    if user_open_id:
        grant_edit_permission(token, doc_id, user_open_id)

    print(json.dumps({"doc_url": f"https://feishu.cn/docx/{doc_id}", "doc_id": doc_id}, ensure_ascii=False))


if __name__ == "__main__":
    main()
