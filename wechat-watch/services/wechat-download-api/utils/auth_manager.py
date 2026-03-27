#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2026 tmwgsicp
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file in the project root for full license text.
# SPDX-License-Identifier: AGPL-3.0-only
"""
认证管理器 - FastAPI版本
管理微信登录凭证（Token、Cookie等）
"""

import os
import time
from pathlib import Path
from typing import Optional, Dict
from dotenv import load_dotenv, set_key

class AuthManager:
    """认证管理单例类"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AuthManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 设置.env文件路径（python-api目录下）
        self.base_dir = Path(__file__).parent.parent
        self.env_path = self.base_dir / ".env"
        
        # 加载环境变量
        self._load_credentials()
        self._initialized = True
    
    def _load_credentials(self):
        """从.env文件加载凭证"""
        if self.env_path.exists():
            load_dotenv(self.env_path, override=True)
        
        self.credentials = {
            "token": os.getenv("WECHAT_TOKEN", ""),
            "cookie": os.getenv("WECHAT_COOKIE", ""),
            "fakeid": os.getenv("WECHAT_FAKEID", ""),
            "nickname": os.getenv("WECHAT_NICKNAME", ""),
            "expire_time": int(os.getenv("WECHAT_EXPIRE_TIME") or 0)
        }
    
    def save_credentials(self, token: str, cookie: str, fakeid: str, 
                        nickname: str, expire_time: int) -> bool:
        """
        保存凭证到.env文件
        
        Args:
            token: 微信Token
            cookie: 微信Cookie
            fakeid: 公众号ID
            nickname: 公众号名称
            expire_time: 过期时间（毫秒时间戳）
        
        Returns:
            保存是否成功
        """
        try:
            # 更新内存中的凭证
            self.credentials.update({
                "token": token,
                "cookie": cookie,
                "fakeid": fakeid,
                "nickname": nickname,
                "expire_time": expire_time
            })
            
            # 确保.env文件存在
            if not self.env_path.exists():
                self.env_path.touch()
            
            # 保存到.env文件
            env_file = str(self.env_path)
            set_key(env_file, "WECHAT_TOKEN", token)
            set_key(env_file, "WECHAT_COOKIE", cookie)
            set_key(env_file, "WECHAT_FAKEID", fakeid)
            set_key(env_file, "WECHAT_NICKNAME", nickname)
            set_key(env_file, "WECHAT_EXPIRE_TIME", str(expire_time))
            
            print(f"✅ 凭证已保存到: {self.env_path}")
            return True
        except Exception as e:
            print(f"❌ 保存凭证失败: {e}")
            return False
    
    def get_credentials(self) -> Optional[Dict[str, any]]:
        """
        获取有效的凭证
        
        Returns:
            凭证字典，如果未登录则返回None
        """
        # 重新加载以获取最新的凭证
        self._load_credentials()
        
        if not self.credentials.get("token") or not self.credentials.get("cookie"):
            return None
        
        return self.credentials
    
    def get_token(self) -> Optional[str]:
        """获取Token"""
        creds = self.get_credentials()
        return creds["token"] if creds else None
    
    def get_cookie(self) -> Optional[str]:
        """获取Cookie"""
        creds = self.get_credentials()
        return creds["cookie"] if creds else None
    
    def get_status(self) -> Dict:
        """
        获取登录状态
        
        Returns:
            状态字典
        """
        # 重新加载凭证
        self._load_credentials()
        
        if not self.credentials.get("token") or not self.credentials.get("cookie"):
            return {
                "authenticated": False,
                "loggedIn": False,
                "account": "",
                "status": "未登录，请先扫码登录"
            }
        
        # 检查是否过期
        expire_time = self.credentials.get("expire_time", 0)
        current_time = int(time.time() * 1000)  # 转换为毫秒
        is_expired = expire_time > 0 and current_time > expire_time
        
        return {
            "authenticated": True,
            "loggedIn": True,
            "account": self.credentials.get("nickname", ""),
            "nickname": self.credentials.get("nickname", ""),
            "fakeid": self.credentials.get("fakeid", ""),
            "expireTime": expire_time,
            "isExpired": is_expired,
            "status": "登录可能已过期，建议重新登录" if is_expired else "登录正常"
        }
    
    def clear_credentials(self) -> bool:
        """
        清除凭证
        
        Returns:
            清除是否成功
        """
        try:
            # 清除内存中的凭证
            self.credentials = {
                "token": "",
                "cookie": "",
                "fakeid": "",
                "nickname": "",
                "expire_time": 0
            }
            
            # 清除进程环境变量中残留的凭证
            env_keys = [
                "WECHAT_TOKEN", "WECHAT_COOKIE", "WECHAT_FAKEID",
                "WECHAT_NICKNAME", "WECHAT_EXPIRE_TIME"
            ]
            for key in env_keys:
                os.environ.pop(key, None)
            
            # 清空 .env 文件中的凭证字段（保留其他配置）
            if self.env_path.exists():
                env_file = str(self.env_path)
                for key in env_keys:
                    set_key(env_file, key, "")
                print(f"✅ 凭证已清除: {self.env_path}")
            
            return True
        except Exception as e:
            print(f"❌ 清除凭证失败: {e}")
            return False

# 创建全局单例
auth_manager = AuthManager()
