---
name: md-to-wechat
description: >
  将本地 Markdown 文章渲染为微信公众号格式并一键推送到草稿箱的完整工作流。
  当用户说"把这篇文章推到公众号"、"发布到微信公众号"、"推送草稿"、
  "帮我发公众号"、"同步到公众号草稿箱"、"推到微信"等类似需求时，
  必须主动使用此 skill，不要跳过。
  使用 publish.cjs 一步完成渲染 + 推送，无需生成本地 HTML 文件。
  需要 Node.js 18+，零外部依赖。
---

# md-to-wechat Skill

将本地 Markdown 文章渲染为微信公众号样式 HTML，并自动推送到公众号草稿箱。

**首次使用**：编辑 Skill 目录下的 `.env` 文件填入配置，详见 `references/setup.md`

---

## Skill 目录结构

本 Skill 安装后的完整目录如下（`<SKILL_DIR>` 为 SKILL.md 所在目录的绝对路径）：

```
<SKILL_DIR>/
├── SKILL.md                  ← 本文件
├── .env                      ← 填写你的配置（必须）
├── .cache.json               ← 运行时自动生成，缓存已上传图片
├── references/
│   └── setup.md              ← 首次配置详细说明
└── scripts/
    ├── publish.cjs           ← 主脚本：渲染 + 推送一步完成
    └── list_themes.cjs       ← 辅助：查询可用主题 ID
```

**AI 如何确定 `<SKILL_DIR>`**：本文件（SKILL.md）所在的目录即为 `<SKILL_DIR>`。AI 工具读取本文件时，可从文件路径中直接获取目录部分。例如，若本文件路径为 `C:\Users\alice\.cursor\skills\md-to-wechat\SKILL.md`，则 `<SKILL_DIR>` = `C:\Users\alice\.cursor\skills\md-to-wechat`。

---

## AI 执行指南

按以下流程执行，每步均为必要步骤，不得跳过：

1. **确认前置配置**：读取 `<SKILL_DIR>/.env`，检查 `ACCOUNT`、`THEME_ID`、`WECHAT_APP_ID`、`WECHAT_APP_SECRET` 是否已填写（非占位符）。如有未填项，告知用户参考 `references/setup.md` 完成配置后再继续。

2. **确认 MD 文件路径**：从对话上下文或 @引用 获取 MD 文件的绝对路径。

3. **一次性确认 IP + 文章信息**：
   - 如果用户明确表示"IP 已加好"，跳到步骤 4。
   - 否则运行一次（无 `--confirmed`）获取本机 IP：
     ```bash
     node "<SKILL_DIR>/scripts/publish.cjs" --file "<md文件绝对路径>"
     ```
   - 同时读取 MD 文件和 `.env`，提取以下信息，**一次性**呈现给用户确认：
     ```
     📌 请确认以下信息，全部 OK 后统一告诉我：

     1. IP 白名单：请将 <上方打印的 IPv4> 加入公众号后台 → 基础信息 → API IP 白名单
     2. 文章标题：《XXX》（如需修改请告知）
     3. 作者名称：YYY（如需修改请告知；为空则草稿中作者栏留空）
     4. 封面图：<来源>（如需修改请提供 URL 或本地路径）
     ```
   - **封面图来源**按以下优先级确定并告知用户：
     - MD 文件中有图片 → 显示「使用 MD 中第一张图片：<URL>」
     - MD 无图片但 `.env` 的 `WECHAT_DEFAULT_COVER` 已填写 → 显示「使用兜底封面：<URL>」
     - 两者均为空 → 显示「⚠️ 未找到封面图，请提供图片 URL 或本地路径，否则推送会失败」并强制等待用户提供
   - 等待用户**一次**回复，收集所有修改意见后再继续。

4. **正式推送**：加 `--confirmed` 运行，根据用户反馈传入对应参数：
   ```bash
   node "<SKILL_DIR>/scripts/publish.cjs" \
     --file "<md文件绝对路径>" \
     --confirmed \
     [--title "标题"] [--author "作者"] [--cover "封面图URL或路径"]
   ```
   成功输出：
   ```json
   { "success": true, "media_id": "XXXX", "title": "文章标题", "message": "草稿已推送成功..." }
   ```

5. **推送成功**：告知用户「✅ 草稿已推送，请前往公众号后台 → 草稿箱查看」

---

## 常见错误处理

| 错误码 | 含义 | 处理方式 |
|--------|------|---------|
| `40164` | IP 不在白名单 | 重新运行 publish.cjs（无 --confirmed）查询当前 IP，更新公众号后台白名单 |
| `missing_env` | .env 未配置或缺字段 | 检查 `.env` 文件，参考 `references/setup.md` |
| `api_error` | 账号/主题 ID 错误 | 运行 `list_themes.cjs` 确认 THEME_ID |
| `file_not_found` | 文件不存在 | 确认 MD 文件路径正确 |
| `cover_download_failed` | 封面图无法下载 | 检查图片 URL 是否可访问，或用 `--cover` 指定本地图片 |

---

## 辅助工具

**查询主题列表**（首次配置时使用）：

```bash
node "<SKILL_DIR>/scripts/list_themes.cjs"
```

输出所有主题名称和 ID，将目标 ID 填入 `.env` 的 `THEME_ID`。

---

## 参数速查

**publish.cjs**

| 参数 | 必填 | 说明 |
|------|------|------|
| `--file` | ✅ | MD 文件路径 |
| `--confirmed` | 否 | 跳过 IP 检查，直接渲染并推送 |
| `--title` | 否 | 指定文章标题，覆盖 MD 中的一级标题 |
| `--author` | 否 | 指定作者名称，覆盖 `.env` 中的 `AUTHOR_NAME` |
| `--cover` | 否 | 指定封面图（URL 或本地路径），覆盖自动检测 |
