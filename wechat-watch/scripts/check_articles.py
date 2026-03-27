#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查公众号文章更新脚本
从 SQLite 缓存读取指定时间段的文章，输出飞书格式的推送内容
"""

import sqlite3
import json
import sys
import io
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 数据库路径
DB_PATH: Path = Path(__file__).parent.parent / "services" / "wechat-download-api" / "data" / "rss.db"
PUSHED_FILE: Path = Path(__file__).parent.parent / "data" / "pushed_articles.json"

def get_time_range() -> tuple[int, int, str]:
    """获取查询时间段"""
    now: datetime = datetime.now()
    hour: int = now.hour
    
    if hour < 10:
        # 早上10点前：前一天18点到当天10点
        start_time: int = int((now - timedelta(hours=16)).replace(hour=18, minute=0, second=0, microsecond=0).timestamp())
        end_time: int = int(now.replace(hour=10, minute=0, second=0, microsecond=0).timestamp())
        time_desc: str = f"{(now - timedelta(days=1)).strftime('%Y-%m-%d')} 18:00 ~ {now.strftime('%Y-%m-%d')} 10:00"
    elif hour < 18:
        # 10点到18点：当天10点到当前时间
        start_time = int(now.replace(hour=10, minute=0, second=0, microsecond=0).timestamp())
        end_time = int(now.timestamp())
        time_desc = f"{now.strftime('%Y-%m-%d')} 10:00 ~ {now.strftime('%Y-%m-%d')} {now.strftime('%H:%M')}"
    else:
        # 18点后：当天10点到18点
        start_time = int(now.replace(hour=10, minute=0, second=0, microsecond=0).timestamp())
        end_time = int(now.replace(hour=18, minute=0, second=0, microsecond=0).timestamp())
        time_desc = f"{now.strftime('%Y-%m-%d')} 10:00 ~ {now.strftime('%Y-%m-%d')} 18:00"
    
    return start_time, end_time, time_desc

def load_pushed_articles() -> set[str]:
    """加载已推送的文章ID"""
    if not PUSHED_FILE.exists():
        return set()
    
    try:
        with open(PUSHED_FILE, 'r', encoding='utf-8') as f:
            data: dict[str, Any] = json.load(f)
            return set(data.get('pushed_ids', []))
    except Exception as e:
        print(f"读取推送记录失败: {e}")
        return set()

def save_pushed_articles(pushed_ids: set[str], start_time: int, end_time: int) -> None:
    """保存已推送的文章ID"""
    PUSHED_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    data: dict[str, Any] = {
        'pushed_ids': list(pushed_ids),
        'last_check': datetime.now().isoformat(),
        'last_time_range': {
            'start': datetime.fromtimestamp(start_time).isoformat(),
            'end': datetime.fromtimestamp(end_time).isoformat()
        }
    }
    
    with open(PUSHED_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_articles_from_db(start_time: int, end_time: int) -> list[dict[str, Any]]:
    """从数据库获取文章"""
    if not DB_PATH.exists():
        print(f"数据库文件不存在: {DB_PATH}")
        return []
    
    conn: sqlite3.Connection = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    try:
        cursor: sqlite3.Cursor = conn.execute("""
            SELECT a.*, s.nickname
            FROM articles a
            JOIN subscriptions s ON a.fakeid = s.fakeid
            WHERE a.publish_time BETWEEN ? AND ?
            ORDER BY a.publish_time DESC
        """, (start_time, end_time))
        
        articles: list[dict[str, Any]] = [dict(row) for row in cursor]
        return articles
    except Exception as e:
        print(f"查询数据库失败: {e}")
        return []
    finally:
        conn.close()

def format_articles(articles: list[dict[str, Any]], time_desc: str) -> str:
    """格式化文章为飞书推送格式"""
    if not articles:
        return f"📰 公众号文章更新\n查询时间范围：{time_desc}\n\n暂无新文章更新。"
    
    # 按公众号分组
    by_account: dict[str, list[dict[str, Any]]] = {}
    for article in articles:
        nickname: str = article.get('nickname', '未知公众号')
        if nickname not in by_account:
            by_account[nickname] = []
        by_account[nickname].append(article)
    
    # 构建输出
    output: str = f"📰 公众号文章更新（{len(articles)} 篇）\n"
    output += f"查询时间范围：{time_desc}\n\n"
    output += "---\n\n"
    
    for nickname, account_articles in by_account.items():
        output += f"**【{nickname}】**\n\n"
        
        for article in account_articles:
            title: str = article.get('title', '无标题')
            content: str = article.get('plain_content', '')
            # 截取前100个字符作为总结
            summary: str = content[:100] + '...' if len(content) > 100 else content
            link: str = article.get('link', '')
            
            output += f"- **文章标题**：{title}\n"
            if summary:
                output += f"- **内容总结**：{summary}\n"
            if link:
                output += f"- **原文链接**：[链接]({link})\n"
            output += "\n"
        
        output += "---\n\n"
    
    return output.strip()

if __name__ == "__main__":
    # 获取时间段
    start_time, end_time, time_desc = get_time_range()
    print(f"查询时间段: {time_desc}")
    print(f"时间戳范围: {start_time} ~ {end_time}")
    print()
    
    # 加载已推送的文章
    pushed_ids: set[str] = load_pushed_articles()
    print(f"已推送文章数: {len(pushed_ids)}")
    
    # 从数据库获取文章
    articles: list[dict[str, Any]] = get_articles_from_db(start_time, end_time)
    print(f"数据库中文章数: {len(articles)}")
    
    # 过滤已推送的文章
    new_articles: list[dict[str, Any]] = []
    for article in articles:
        # 使用文章ID（如果存在）或标题作为唯一标识
        article_id: str = article.get('id') or article.get('title', '')
        if article_id not in pushed_ids:
            new_articles.append(article)
    
    print(f"新文章数: {len(new_articles)}")
    print()
    
    # 格式化输出
    output: str = format_articles(new_articles, time_desc)
    print(output)
    
    # 更新推送记录
    for article in new_articles:
        article_id = article.get('id') or article.get('title', '')
        pushed_ids.add(article_id)
    
    save_pushed_articles(pushed_ids, start_time, end_time)
    print(f"\n已更新推送记录，当前共 {len(pushed_ids)} 篇")
