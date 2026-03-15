---
name: scrapling-article-fetch
description: 使用 Scrapling + html2text 从 URL 抓取可读正文（含图片），按优先级选择器提取并按字符数截断；随后自动写入飞书文档并返回文档链接。适用于用户发送文章/博客/新闻链接（尤其是微信公众号 mp.weixin.qq.com）并希望快速验收正文内容的场景。
---

将文章正文抓取为 Markdown，并按需要写入飞书文档供用户验收。

## 前提条件

1. Python 3.10+。
2. 运行环境满足以下其一：
   - 推荐：已安装 `uv`
   - 备选：可用的 `venv + pip`
3. 机器可访问目标 URL。
4. 如需写飞书文档，默认直接使用 skill 内脚本按“当前 agent 身份”直连 Feishu OpenAPI；不要手动传 `app_id` / `app_secret`。

## 环境检查（必须先做）

在真正抓取前，先检查当前环境是否具备 Python。不要假设系统一定有 `python` 别名；统一先跑 wrapper：

```bash
bash ~/.openclaw/skills/scrapling-article-fetch/scripts/run_pipeline.sh
```

这个 wrapper 会优先选 `python3`，其次 `python`，避免再次出现“环境有 Python，但入口命令写死导致误判”的问题。

执行规则：
- 若 `python_ok=true`：继续执行抓取。
- 若没有 Python 或版本低于 3.10：先提醒用户安装，或在征得用户同意后再帮装；不要直接跳过检查硬跑。
- 若没有 `uv` 但有可用 Python：可以继续，只是改用 `venv + pip` 方案。

## 执行命令（抓取）

在受管控 Python 环境中，优先使用 `uv`：

```bash
uv run --with 'scrapling[fetchers]' --with html2text python ~/.openclaw/skills/scrapling-article-fetch/scripts/scrapling_fetch.py <url> [max_chars]
```

默认 `max_chars=30000`。

## 执行方式（Markdown → 飞书文档）

当需要把抓取结果写入飞书文档时，默认仍使用 `md_to_feishu_doc.py`，但**不要让模型自由手写标题字符串**。

推荐调用方式：

```bash
python3 ~/.openclaw/skills/scrapling-article-fetch/scripts/md_to_feishu_doc.py <article_json_or_title> <src_url> <markdown_file> [doc_id] [user_open_id]
```

说明：
- 第 1 个参数既可以传标题字符串，也可以直接传 `scrapling_fetch.py --json` 产出的 `.json` 文件路径。
- **飞书场景默认应传 `.json` 文件路径**，让写文档脚本直接读取其中的 `title` 字段；不要让模型自己概括标题。
- 如果传入的是普通标题字符串，但它明显像正文第一句/小标题，脚本会自动降级，从 Markdown 中再取标题，减少新 agent 传错标题的概率。
- `user_open_id` 建议传当前用户 open_id，脚本会自动补编辑权限。
- `doc_id` 可选；传入时表示覆盖更新已有文档，不传则新建文档。
- 飞书写入脚本只负责把**上游已经产出的 Markdown**稳定写入文档；不要在写入阶段再自行抓原网页补封面，封面缺失要回到上游抓取脚本修。

## 抓取规则

脚本必须按以下逻辑执行：

1. 使用 `Fetcher.get()` 拉取页面 HTML。
2. 如果域名是微信公众号（`mp.weixin.qq.com`），优先尝试：
   - `#js_content`
   - `.rich_media_content`
   - `.rich_media_area_primary`
3. 再尝试通用选择器：
   - `article`
   - `main`
   - `.post-content`
   - `[class*="body"]`
4. 用 `html2text` 转为 Markdown。
5. 默认保留链接和图片。
6. 清理常见微信尾部噪音（扫码提示、授权弹窗等文案）。
7. 按 `max_chars` 截断。
8. 若未命中正文容器，回退为整页 HTML 转换结果。

## 默认交付流程（必须执行）

当用户让你抓取公众号/文章时，默认执行以下流程，不需要额外确认：

1. 先检查运行环境：
   - 是否有 Python 3.10+
   - 是否可用 `uv` 或 `venv + pip`
   - 如果没有 Python，不要假设用户环境已具备；应先提醒用户安装，或在征得用户同意后再帮装。
2. 运行抓取脚本，得到 Markdown 和 JSON。
3. 判断当前聊天渠道：
   - 如果当前在飞书，默认调用 `md_to_feishu_doc.py`，并把抓取生成的 `.json` 文件路径作为第 1 个参数传入，按当前 agent 身份创建并写入飞书文档
   - 调用时传当前用户 open_id，确保用户自动拿到编辑权限
   - 不要让模型自己拼标题参数
   - 如果不在飞书，为保证用户体验，直接把抓取结果以 Markdown 代码块形式回复给用户，而不是返回飞书链接

### 非飞书场景回复模板

当当前渠道不是飞书时，直接使用脚本生成代码块回复：

```bash
python3 ~/.openclaw/skills/scrapling-article-fetch/scripts/render_markdown_reply.py <title> <url> <markdown_file>
```

如果当前机器没有 `python3` 但有 `python`，则改用 `python`。实际执行时优先复用前面 wrapper 已选出的解释器，不要手写死。

输出格式固定为：

````markdown
```markdown
# <文章标题>

原文链接：<url>

<完整 Markdown 正文>
```
````

不要再额外创建飞书文档，也不要只回一个链接。

4. 将完整抓取结果交付给用户，至少包含：
   - 原文链接
   - 标题
   - 完整正文（含图片）

仅当用户明确说“不要写飞书文档”时，才只返回文本。

## 备注

- 如果页面高度依赖 JS 导致抓取为空，后续可切换 DynamicFetcher 变体。
- 输出格式保持稳定，便于与原文逐段对照验收。
- 默认写飞书文档时，由脚本自动解析当前 agent 对应的飞书账号并直连 Feishu OpenAPI；不要手动传凭证。
