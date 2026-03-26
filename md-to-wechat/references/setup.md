# md-to-wechat Skill 首次配置指南

本文件面向首次使用此 Skill 的用户，详细说明每一步配置。

---

## 第一步：编辑 .env 文件

打开 Skill 目录下的 `.env` 文件，填写你的真实配置：

```
<SKILL_DIR>/.env
```

---

## 第二步：注册 feishu2weixin 账号并获取主题 ID

1. 访问 https://feishu2weixin.maolai.cc 注册账号（支持邮箱或手机号）
2. 登录后，进入「主题」页面，选择或创建一个喜欢的主题
3. 在「我的主题」中点击主题，复制主题 ID

将以下信息填入 `.env`：

```bash
ACCOUNT=你的邮箱或手机号
THEME_ID=从网站复制的主题ID
```

**或者**，让 AI 帮你查询主题列表：

```bash
node "<SKILL_DIR>/scripts/list_themes.cjs"
```

输出示例：

```
主题列表：

  1. 科技蓝
     ID：42e01ab035fa3bc914ac1d44c191e6d8

  2. 简约白
     ID：8f3a9c21b4e7d5f012345678abcdef90

共 2 个主题。将目标主题 ID 填入 .env 的 THEME_ID 字段。
```

---

## 第三步：填写微信公众号凭据

登录微信公众平台（https://mp.weixin.qq.com），进入：
**设置与开发 → 基本配置**

找到以下信息填入 `.env`：

```bash
WECHAT_APP_ID=你的AppID
WECHAT_APP_SECRET=你的AppSecret
```

> **安全提示**：AppSecret 仅保存在本地 `.env` 文件，不会上传到任何云端服务。

---

## 第四步：配置 IP 白名单

微信公众号 API 需要将调用接口的机器 IP 加入白名单，否则会报 `40164` 错误。

### 查询本机公网 IPv4

在命令行运行以下任一命令：

**PowerShell（Windows）：**
```powershell
(Invoke-WebRequest -UseBasicParsing -Uri "https://api4.ipify.org").Content
```

**或者直接运行 render.cjs（会自动检测并显示 IP）：**
```bash
node "<SKILL_DIR>/scripts/render.cjs" --file <任意md文件>
```

### 添加到白名单

1. 登录微信公众平台：https://mp.weixin.qq.com
2. 进入：**设置与开发 → 基本配置**
3. 找到「API IP 白名单」，点击「查看」
4. 点击「修改」，将你的 IPv4 地址填入（每行一个）
5. 点击「确定」保存

> **注意**：
> - 只支持 IPv4，不支持 IPv6
> - 换 Wi-Fi 或热点后 IP 会变，需要重新配置
> - 如果报 40164 错误，先重新查询 IP，更新白名单后再试

---

## 第五步：（可选）设置默认作者名称

在 `.env` 中填写公众号的作者名称，每篇文章推送时自动带上：

```bash
AUTHOR_NAME=你的名字或公众号名称
```

留空则草稿中作者栏为空（公众号后台可手动补填）。也可在每次推送时通过 `--author` 参数临时指定。

---

## 第六步：（可选）自定义兜底封面图

当文章中没有图片时，会使用 `WECHAT_DEFAULT_COVER` 作为封面。

默认已配置一张示例图片，如需替换，在 `.env` 中修改：

```bash
WECHAT_DEFAULT_COVER=https://你的图片URL
```

建议使用尺寸 900×383 像素、2MB 以内的 JPG/PNG 图片。

---

## 完成！开始使用

配置完成后，告诉 AI：

> "把这篇文章推到公众号草稿"

AI 会自动执行两步流程：
1. 运行 `render.cjs` 渲染文章
2. 运行 `push_draft.cjs` 推送到草稿箱

---

## 常见问题

| 错误 | 原因 | 解决方法 |
|------|------|---------|
| `40164` | IP 不在白名单 | 重新查询本机 IP，更新公众号后台白名单 |
| `missing_env` | .env 未配置 | 检查 .env 文件是否存在并填写完整 |
| `api_error` | 账号或主题 ID 错误 | 运行 `list_themes.cjs` 确认 THEME_ID |
| `cover_download_failed` | 封面图 URL 无法访问 | 检查 WECHAT_DEFAULT_COVER 是否可以访问 |
| `file_not_found` | 文件路径错误 | 确认 MD 文件路径正确 |
