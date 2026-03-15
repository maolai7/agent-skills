# 🤖 Agent Skills

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 一个精心整理的 AI Agent 技能集合，帮助你的智能助手完成更多实用任务。

## 📚 技能列表

| 技能名称 | 描述 | 适用场景 |
|---------|------|---------|
| [scrapling-article-fetch](./scrapling-article-fetch) | 智能抓取网页文章内容并转换为 Markdown，支持自动写入飞书文档 | 文章整理、内容归档、公众号文章提取 |

## 🚀 快速开始

每个技能都包含独立的 `SKILL.md` 文档，详细说明了：
- 功能特性
- 安装要求
- 使用方法
- 配置说明

点击上方表格中的技能名称即可查看详细文档。

## 📁 项目结构

```
agent-skills/
├── README.md              # 本文件
├── scrapling-article-fetch/    # 文章抓取技能
│   ├── SKILL.md          # 技能说明文档
│   ├── scripts/          # 执行脚本
│   └── evals/            # 评估测试
└── ...                   # 更多技能（持续添加中）
```

## 🤝 如何贡献

欢迎提交新的 Agent Skills！请确保：

1. 在根目录创建独立的技能文件夹
2. 包含详细的 `SKILL.md` 说明文档
3. 提供必要的脚本和测试用例
4. 更新本 README 的技能列表

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源协议。

---

> 💡 **提示**: 这些技能主要为 AI Agent（如 Claude、GPT 等）设计，用于扩展其能力边界。
