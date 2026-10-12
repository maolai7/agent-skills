---
name: scrapling-article-fetch
description: 使用 Scrapling + html2text 抓取文章正文并转成 Markdown/JSON，适合处理文章、博客、新闻和微信公众号链接，尤其适合“帮我抓这篇公众号文章”“读取这篇文章正文”“把这篇链接转成 Markdown”“抓完后写进飞书文档”这类请求。
---

把文章正文抓成 Markdown / JSON，并默认归档到本地，方便后续回看或继续加工。

## 一句话怎么用

默认先检查环境，再抓文章。

```bash
python scripts/check_env.py
python scripts/fetch_article.py <url>
```

如果要 JSON：

```bash
python scripts/fetch_article.py <url> --json
```

## 这个 skill 负责什么

这个 skill 解决 3 件事：

1. 检查当前机器是否具备可用的 Python 抓取环境
2. 抓取文章正文，输出 Markdown 或 JSON
3. 默认把抓取结果归档到本地；如当前在飞书，可继续写进飞书文档

这个 skill 不负责：

1. 安装 Python 本身
2. 解释文章内容
3. 改写文章
4. 兜底处理所有强 JS / 登录态页面

## 推荐流程

默认按下面顺序执行：

1. 先检查环境
2. 再抓文章
3. 先确认本地文件已落盘
4. 飞书场景再写飞书文档
5. 非飞书场景直接回 Markdown 代码块

不要跳过环境检查直接硬跑。

## 目录约定

以下命令默认都以**当前 skill 目录**为执行基准。

例如：

```bash
python scripts/check_env.py
python scripts/fetch_article.py <url> --json
```

## 本地输出规则

抓取成功后，脚本会**自动**把结果存到本地，默认不需要手动传路径。

默认保存规则：

1. 从当前执行目录逐级向上找，遇到带 `.git` 的目录即视为项目根
2. 保存到项目根下的：`Temp/scrapling-article-fetch/YYYY/MM/YYYY-MM-DD/`
3. 目录不存在时自动新建
4. 如果不在任何项目内，则回退到系统临时目录（同样自动新建）
5. 保存完成后，向 stderr 打印一行 `[saved] <文件路径>`，方便后续步骤直接引用

以 `D:\ProjectAI\maolai\WorkBuddyGO` 为例，落盘位置形如：

```text
D:\ProjectAI\maolai\WorkBuddyGO\Temp\scrapling-article-fetch\2026\10\2026-10-12\<文章标题>.md
```

默认产物：

1. `<文章标题>.md`
2. `<文章标题>.json`（供飞书写文档脚本读取标题等结构化字段）

说明：

1. 同一篇文章重复抓取时，直接按同名文件覆盖
2. 文件名默认使用文章标题；如果标题里有 Windows 非法字符，脚本会自动做最小清洗
3. 控制台仍会继续输出 Markdown 或 JSON，方便当前对话直接使用

只有需要覆盖默认位置时才传 `--output-root`：

```bash
python scripts/fetch_article.py <url> --output-root D:\somewhere\outputs
```

如果这次只想打印，不想落盘：

```bash
python scripts/fetch_article.py <url> --no-save
```

## 第一步：检查环境

先执行：

```bash
python scripts/check_env.py
```

如果当前机器没有 `python` 但有 `python3`，则改用：

```bash
python3 scripts/check_env.py
```

这个命令会输出 JSON，重点看：

1. `python_ok`
2. `uv_found`
3. `venv_available`

判断规则：

1. `python_ok=true`：可以继续抓取
2. `python_ok=false`：先提醒用户安装或升级 Python
3. `uv_found=true`：优先走 `uv`
4. `uv_found=false`：允许回退到当前 Python 环境执行

如果没有 Python 或版本低于 3.10，不要继续抓取。

## 第二步：抓取文章

统一入口：

```bash
python scripts/fetch_article.py <url> [max_chars]
```

如果当前机器没有 `python` 但有 `python3`，则改用：

```bash
python3 scripts/fetch_article.py <url> [max_chars]
```

如果要 JSON：

```bash
python scripts/fetch_article.py <url> [max_chars] --json
```

说明：

1. 默认 `max_chars=30000`
2. 入口内部固定先拿 JSON，再按你的参数决定输出 Markdown 还是 JSON
3. 如果机器没有 `uv`，则回退到当前 Python 环境直接执行 `scrapling_fetch.py`
4. 脚本会自动把标准输出切到 UTF-8，避免 Windows 下公众号正文因为 `GBK` 编码输出失败
5. 成功时会先落本地，再输出正文或 JSON；失败时才输出错误

## 抓取结果长什么样

### Markdown 输出

默认输出正文 Markdown，通常包含：

1. 标题图 Markdown
2. 正文内容
3. 标题层级
4. 图片链接

### JSON 输出

`--json` 输出字段固定为：

1. `title`
2. `cover_url`
3. `markdown`

## 抓取实现规则

底层抓取逻辑在 `scripts/scrapling_fetch.py`，默认规则如下：

1. 先用 `Fetcher.get()` 拉页面
2. 微信公众号优先尝试：
   - `#js_content`
   - `.rich_media_content`
   - `.rich_media_area_primary`
3. 再尝试通用正文容器：
   - `article`
   - `main`
   - `.post-content`
   - `[class*="body"]`
4. 用 `html2text` 转 Markdown
5. 保留链接和图片
6. 清理常见微信尾部噪音
7. 按 `max_chars` 截断
8. 如果没命中正文容器，就回退到整页 HTML 转换结果

## 飞书场景

如果当前在飞书，默认继续把抓取结果写入飞书文档。

调用方式：

```bash
python scripts/md_to_feishu_doc.py <article_json_or_title> <src_url> <markdown_file> [doc_id] [user_open_id]
```

优先规则：

1. 第 1 个参数优先传 `.json` 文件路径
2. 不要让模型自己拼标题
3. `user_open_id` 优先传当前用户 open_id，确保用户自动拿到编辑权限

这个脚本负责：

1. 创建或更新飞书文档
2. 写入标题、原文链接、正文、图片
3. 给当前用户补编辑权限

这个脚本不负责：

1. 重新抓原网页
2. 猜标题
3. 修补上游抓取失败

## 非飞书场景

如果当前不在飞书，直接把正文回成 Markdown 代码块，不要返回飞书链接。

调用方式：

```bash
python scripts/render_markdown_reply.py <title> <url> <markdown_file>
```

输出格式固定为：

````markdown
```markdown
# <文章标题>

原文链接：<url>

<完整 Markdown 正文>
```
````

## 默认交付规则

当用户说“抓这篇文章”“抓公众号正文”“帮我读取这篇链接”时，默认执行：

1. 跑 `scripts/check_env.py`
2. 跑 `scripts/fetch_article.py`
3. 优先使用本地归档结果
4. 飞书场景写飞书文档
5. 非飞书场景直接回 Markdown

除非用户明确说：

1. 不要飞书文档
2. 只要文字
3. 只要 JSON
4. 不要本地保存

否则按默认交付规则执行。

## 常见判断

### 可以继续执行

出现下面这些情况，可以继续：

1. `python_ok=true`
2. 抓取结果里有 `title`
3. 抓取结果里有非空 `markdown`

### 应该停下来

出现下面这些情况，应该停下来并告诉用户：

1. 没有 Python
2. Python 版本低于 3.10
3. 页面返回错误状态
4. 抓取输出为空且没有有效正文

### 需要回到上游修

如果出现下面这些情况，不要在飞书写入阶段补救：

1. 标题错了
2. 封面图没抓到
3. 正文不完整
4. 图片链接缺失

这些都应该回到 `scripts/fetch_article.py` / `scripts/scrapling_fetch.py` 这一层解决。

## 备注

1. 这个 skill 的主入口是 Python，不再依赖 PowerShell 或 bash 包一层
2. `fetch_article.py` 是统一抓取入口
3. `scrapling_fetch.py` 是底层抓取实现
4. `check_env.py` 只负责环境检查
5. `fetch_article.py` 负责“抓取编排 + 本地落盘 + 控制台输出”

