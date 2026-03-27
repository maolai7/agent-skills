#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2026 tmwgsicp
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file in the project root for full license text.
# SPDX-License-Identifier: AGPL-3.0-only
"""
代理池管理
支持多 VPS 自建代理（SOCKS5/HTTP）轮转，分散请求 IP。
失败的代理会被临时标记为不可用，一段时间后自动恢复探测。

配置方式（.env）：
    PROXY_URLS=socks5://ip1:port,http://ip2:port,socks5://user:pass@ip3:port

留空则不使用代理。
"""

import logging
import os
import time
import threading
from typing import Optional, List

logger = logging.getLogger(__name__)

FAIL_COOLDOWN = 120


class ProxyPool:
    """带健康检测的轮转代理池"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._proxies: List[str] = []
        self._index = 0
        self._fail_until: dict[str, float] = {}
        self._lock = threading.Lock()
        self._load_proxies()
        self._initialized = True

    def _load_proxies(self):
        raw = os.getenv("PROXY_URLS", "").strip()
        if not raw:
            logger.info("Proxy pool: no proxies configured (direct connection)")
            return

        self._proxies = [p.strip() for p in raw.split(",") if p.strip()]
        logger.info("Proxy pool: loaded %d proxies", len(self._proxies))

    def reload(self):
        """从环境变量重新加载代理列表"""
        with self._lock:
            self._proxies = []
            self._index = 0
            self._fail_until.clear()
            self._load_proxies()

    @property
    def enabled(self) -> bool:
        return len(self._proxies) > 0

    @property
    def count(self) -> int:
        return len(self._proxies)

    def next(self) -> Optional[str]:
        """获取下一个可用代理（跳过冷却中的），全部不可用时返回 None"""
        if not self._proxies:
            return None
        now = time.time()
        with self._lock:
            for _ in range(len(self._proxies)):
                proxy = self._proxies[self._index % len(self._proxies)]
                self._index += 1
                if self._fail_until.get(proxy, 0) <= now:
                    return proxy
        return None

    def get_all(self) -> List[str]:
        return list(self._proxies)

    def mark_failed(self, proxy: str):
        """标记代理失败，冷却一段时间后自动恢复"""
        with self._lock:
            self._fail_until[proxy] = time.time() + FAIL_COOLDOWN
        logger.warning("Proxy %s marked failed, cooldown %ds", proxy, FAIL_COOLDOWN)

    def mark_ok(self, proxy: str):
        """标记代理恢复正常"""
        with self._lock:
            self._fail_until.pop(proxy, None)

    def get_status(self) -> dict:
        """返回代理池状态"""
        now = time.time()
        healthy = []
        failed = []
        for p in self._proxies:
            if self._fail_until.get(p, 0) > now:
                failed.append(p)
            else:
                healthy.append(p)
        return {
            "enabled": self.enabled,
            "total": self.count,
            "healthy": len(healthy),
            "failed": len(failed),
            "failed_proxies": failed,
        }


proxy_pool = ProxyPool()
