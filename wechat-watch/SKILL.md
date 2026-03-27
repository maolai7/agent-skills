---
name: wechat-watch
description: 微信公众号文章订阅与推送。自动部署 wechat-download-api 服务，定时轮询关注的公众号，检测新文章后总结并推送到飞书。触发条件：用户提到"公众号订阅"、"微信文章推送"、"wechat watch"、"公众号更新"等，或由 cron 定时任务触发。前置条件：用户需要有微信公众号（订阅号/服务号均可）用于扫码登录。
---

# 微信公众号订阅与推送

## 功能

1. 自动部署 wechat-download-api 服务
2. 获取登录二维码供用户扫码
3. 定时轮询已订阅公众号
4. 检测新文章，调用 API 获取完整内容
5. 总结文章内容，合并推送到飞书

## 目录结构

```
<skill-dir>/
├── SKILL.md                              ← skill 定义（AI 读取此文件执行）
├── services/
│   └── wechat-download-api/              ← 微信 API 服务
│       ├── app.py                        ← 服务入口
│       └── data/
│           └── rss.db                    ← 文章缓存数据库
├── scripts/
│   └── check_articles.py                 ← 检查新文章脚本
└── data/
    └── pushed_articles.json              ← 已推送文章记录
```

## 前置条件

**用户必须有微信公众号**（订阅号或服务号均可），用于扫码登录获取凭证。

凭证有效期约 4 天，过期后需要重新扫码。

## 执行流程

### 步骤 0：首次使用引导

当用户首次使用此 skill 时：

1. 检查服务是否已部署（检查 `services/wechat-download-api/app.py` 是否存在）
2. 如果未部署，询问用户是否有微信公众号
3. 如果有，自动部署服务
4. 启动服务后，获取登录二维码并发送给用户
5. 等待用户扫码确认
6. 登录成功后，引导用户订阅公众号

### 步骤 1：检查服务状态

```bash
curl -s http://localhost:5000/api/health
```

如果返回非 200，说明服务未启动，需要启动服务。

### 步骤 2：检查登录状态

```bash
curl -s http://localhost:5000/api/admin/status
```

如果未登录：
1. 调用 `/api/login/session/{sessionid}` 创建会话
2. 调用 `/api/login/getqrcode` 获取二维码
3. 将二维码图片发送给用户（使用 MEDIA: 语法）
4. 轮询 `/api/login/check` 等待登录成功

### 步骤 3：管理订阅

**添加订阅：**
1. 调用 `/api/public/searchbiz?query=公众号名称` 搜索公众号
2. 获取 `fakeid`
3. 调用 `/api/rss/subscribe` 添加订阅

**查看订阅：**
```bash
curl -s http://localhost:5000/api/rss/subscriptions
```

**取消订阅：**
```bash
curl -X DELETE http://localhost:5000/api/rss/subscribe/{fakeid}
```

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    wechat-download-api                      │
│                                                             │
│  RSS Poller（每小时自动）                                    │
│      ↓                                                      │
│  轮询订阅的公众号 → 缓存到 SQLite（含完整内容）               │
│                                                             │
│  数据表：                                                   │
│  - subscriptions：订阅列表                                  │
│  - articles：文章缓存（title, content, publish_time 等）    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    wechat-watch skill                       │
│                                                             │
│  Cron (10:00 / 18:00)                                       │
│      ↓                                                      │
│  从 SQLite 读取缓存文章                                     │
│      ↓                                                      │
│  按 publish_time 筛选时间段                                 │
│      ↓                                                      │
│  总结 + 推送到飞书                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**核心设计：利用项目缓存，避免重复请求微信 API**

## 定时任务配置

每天两次检查，按时间段筛选：

| 任务时间 | 查询范围 |
|---------|---------|
| 每天 10:00 | 前一天 18:00 ~ 当天 10:00 |
| 每天 18:00 | 当天 10:00 ~ 当天 18:00 |

**时间段筛选逻辑：**

文章数据有 `publish_time` 字段（Unix 时间戳），按以下方式筛选：

```python
import time
from datetime import datetime, timedelta

# 早上10点任务：前一天18点到当天10点
if hour == 10:
    start_time = int((datetime.now() - timedelta(hours=16)).timestamp())  # 昨天18:00
    end_time = int(datetime.now().replace(hour=10, minute=0, second=0).timestamp())

# 晚上18点任务：当天10点到18点
if hour == 18:
    start_time = int(datetime.now().replace(hour=10, minute=0, second=0).timestamp())
    end_time = int(datetime.now().replace(hour=18, minute=0, second=0).timestamp())

# 筛选文章
for article in articles:
    if start_time <= article['publish_time'] <= end_time:
        # 这是新文章，需要推送
```

### 步骤 4：检查文章更新（定时任务）

**从 SQLite 缓存读取，不请求微信 API：**

```python
import sqlite3
from datetime import datetime, timedelta

# 连接数据库（使用相对路径，基于 skill 目录）
import os
skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # skill 根目录
db_path = os.path.join(skill_dir, "services", "wechat-download-api", "data", "rss.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# 计算时间段
now = datetime.now()
if now.hour == 10:
    # 早上10点：前一天18点到当天10点
    start_time = int((now - timedelta(hours=16)).timestamp())  # 昨天18:00
    end_time = int(now.replace(hour=10, minute=0, second=0).timestamp())
else:
    # 晚上18点：当天10点到18点
    start_time = int(now.replace(hour=10, minute=0, second=0).timestamp())
    end_time = int(now.replace(hour=18, minute=0, second=0).timestamp())

# 从缓存读取文章
cursor = conn.execute("""
    SELECT a.*, s.nickname
    FROM articles a
    JOIN subscriptions s ON a.fakeid = s.fakeid
    WHERE a.publish_time BETWEEN ? AND ?
    ORDER BY a.publish_time DESC
""", (start_time, end_time))

articles = [dict(row) for row in cursor]
conn.close()
```

**流程：**
1. 运行脚本：`python <skill-dir>/scripts/check_articles.py`
2. 脚本输出飞书格式的文章内容
3. **发送给用户**：
   - 有飞书环境 → 通过飞书通道发送给用户
   - 无飞书环境 → 直接在对话中展示内容
4. 更新 `data/pushed_articles.json`
5. 无更新时也要发送："暂无新文章更新"

### 步骤 5：推送格式

**有新文章时：**

```
📰 公众号文章更新（X 篇）
查询时间范围：YYYY-MM-DD HH:00 ~ YYYY-MM-DD HH:00

---

**【公众号名称】**

- **文章标题**：XXX
- **内容总结**：XXX...
- **原文链接**：[链接](URL)

---

**【另一个公众号】**

- **文章标题**：XXX
- **内容总结**：XXX...
- **原文链接**：[链接](URL)
```

**无新文章时：**

```
📰 公众号文章更新
查询时间范围：YYYY-MM-DD HH:00 ~ YYYY-MM-DD HH:00

暂无新文章更新。
```

## API 接口汇总

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/admin/status` | GET | 登录状态 |
| `/api/login/session/{sessionid}` | POST | 创建登录会话 |
| `/api/login/getqrcode` | GET | 获取登录二维码 |
| `/api/login/check` | GET | 检查扫码状态 |
| `/api/public/searchbiz` | GET | 搜索公众号 |
| `/api/public/articles` | GET | 获取文章列表 |
| `/api/article` | POST | 获取文章内容 |
| `/api/rss/subscribe` | POST | 添加订阅 |
| `/api/rss/subscriptions` | GET | 获取订阅列表 |
| `/api/rss/subscribe/{fakeid}` | DELETE | 取消订阅 |

## 部署命令

### 检查环境

```bash
# 检查 Docker
docker --version

# 检查 Python
python3 --version
```

### Docker 部署（推荐）

```bash
cd <skill-dir>/services
git clone https://github.com/tmwgsicp/wechat-download-api.git
cd wechat-download-api
cp env.example .env
docker-compose up -d
```

### Python 部署（无 Docker）

```bash
cd <skill-dir>/services
git clone https://github.com/tmwgsicp/wechat-download-api.git
cd wechat-download-api
bash start.sh
```

## 数据文件

### pushed_articles.json

记录已推送的文章 ID 和上次检查时间，避免重复推送：

```json
{
  "pushed_ids": [
    "article_id_1",
    "article_id_2"
  ],
  "last_check": "2026-03-24T18:00:00+08:00",
  "last_time_range": {
    "start": "2026-03-24T10:00:00+08:00",
    "end": "2026-03-24T18:00:00+08:00"
  }
}
```
```

### subscriptions.json（可选）

如果用户想用自己的订阅管理而不是服务的：

```json
{
  "accounts": [
    {
      "fakeid": "MzA1MjM1ODk2MA==",
      "nickname": "人民日报",
      "alias": "rmrbwx"
    }
  ]
}
```

## 注意事项

1. **登录有效期**：约 4 天，过期后需重新扫码
2. **检查频率**：每天两次（10:00 和 18:00），按时间段筛选
3. **推送目标**：老板私聊，不是群聊
4. **图片发送**：二维码使用 `MEDIA:` 语法发送到飞书
5. **服务端口**：默认 5000，确保端口未被占用
6. **数据持久化**：项目 data 目录需要持久化，避免重启丢失数据
7. **无更新也推送**：每次检查后都要推送结果，无更新则说明"暂无新文章"

## 风控防护脚本

已封装请求逻辑到脚本，自动处理间隔：

```bash
# 运行检查脚本
bash <skill-dir>/scripts/check_articles.sh
```

脚本内置间隔规则：
- 搜索公众号：3 秒
- 获取文章内容：**5 秒**
- 添加订阅：3 秒

**执行时请使用脚本，不要直接调用 API，避免忘记间隔。**

## ⚠️ 风控防护（重要）

**微信会检测频繁请求并触发风控**，返回"请求过于频繁，请4秒后重试"。

**必须遵守以下间隔规则：**

| 操作 | 最小间隔 |
|------|---------|
| 搜索公众号 | 3 秒 |
| 获取文章列表 | 3 秒 |
| 获取文章内容 | **5 秒** |
| 添加订阅 | 3 秒 |

**示例代码：**

```bash
# 获取多篇文章内容时，每次请求后 sleep 5
for url in "${urls[@]}"; do
    curl -s -X POST "http://localhost:5000/api/article" \
        -H "Content-Type: application/json" \
        -d "{\"url\":\"$url\"}"
    sleep 5  # 必须！
done
```

**如果触发风控：**
- 等待 10-30 分钟后重试
- 检查请求间隔是否足够
- 考虑配置代理池（设置 `PROXY_URLS` 环境变量）

## 用户交互指令

用户可以说：
- "帮我订阅公众号 XXX" → 搜索并添加订阅
- "查看我的公众号订阅" → 列出已订阅的公众号
- "取消订阅 XXX" → 取消订阅
- "检查公众号更新" → 手动触发一次轮询
- "重新登录微信" → 获取新二维码扫码

---

## 定时任务配置（推荐）

建议配置两个定时任务，每天自动检查并推送公众号文章更新。

### 任务 1：早上 10:00 推送

检查时间段：**昨天 18:00 ~ 今天 10:00**（16 小时，覆盖晚上 + 早上）

```json
{
  "agentId": "info_collector",
  "name": "公众号文章推送 - 早",
  "schedule": {
    "kind": "cron",
    "expr": "0 10 * * *",
    "tz": "Asia/Shanghai"
  },
  "sessionTarget": "isolated",
  "wakeMode": "now",
  "payload": {
    "kind": "agentTurn",
    "message": "运行公众号文章检查脚本：python3 <skill-dir>/scripts/check_articles.py\n\n脚本会自动从 SQLite 缓存读取指定时间段的文章，输出飞书格式的推送内容。定时任务框架会自动将输出推送到配置的目标用户。"
  },
  "delivery": {
    "mode": "announce",
    "channel": "feishu",
    "to": "user:你的飞书_USER_ID"
  }
}
```

### 任务 2：晚上 18:00 推送

检查时间段：**今天 10:00 ~ 今天 18:00**

```json
{
  "agentId": "info_collector",
  "name": "公众号文章推送 - 晚",
  "schedule": {
    "kind": "cron",
    "expr": "0 18 * * *",
    "tz": "Asia/Shanghai"
  },
  "sessionTarget": "isolated",
  "wakeMode": "now",
  "payload": {
    "kind": "agentTurn",
    "message": "运行公众号文章检查脚本：python3 <skill-dir>/scripts/check_articles.py\n\n脚本会自动从 SQLite 缓存读取指定时间段的文章，输出飞书格式的推送内容。定时任务框架会自动将输出推送到配置的目标用户。"
  },
  "delivery": {
    "mode": "announce",
    "channel": "feishu",
    "to": "user:你的飞书_USER_ID"
  }
}
```

### 配置说明

| 配置项 | 说明 | 如何修改 |
|--------|------|----------|
| `agentId` | 执行任务的 agent | 保持 `info_collector` 或改为你的 agent ID |
| `delivery.to` | 推送目标用户 | **必须修改**为你的飞书 user ID |
| `schedule.expr` | cron 表达式 | 可根据需要调整时间 |

### 如何获取飞书 user ID

1. 在飞书中打开与 bot 的私聊
2. 发送任意消息
3. 查看 OpenClaw 日志或会话信息，找到 `user:ou_xxx` 格式的 ID

### 推送格式

**有新文章时：**
```
📰 公众号文章更新（X 篇）
查询时间范围：2026-03-24 10:00 ~ 2026-03-24 18:00

---

**【公众号名称】**

- **文章标题**：XXX
- **内容总结**：XXX...
- **原文链接**：[链接](URL)
```

**无新文章时：**
```
📰 公众号文章更新
查询时间范围：2026-03-24 10:00 ~ 2026-03-24 18:00

暂无新文章更新。
```

### 设计说明

- **脚本只负责输出内容**：`check_articles.py` 输出飞书格式的 Markdown 到 stdout
- **推送由框架处理**：定时任务的 `delivery` 配置自动将输出推送到目标用户
- **通用性强**：skill 本身不写死 user ID，每个用户只需修改定时任务配置中的 `delivery.to`