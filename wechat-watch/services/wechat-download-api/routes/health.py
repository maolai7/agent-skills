#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2026 tmwgsicp
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file in the project root for full license text.
# SPDX-License-Identifier: AGPL-3.0-only
"""
健康检查路由
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", summary="健康检查")
async def health_check():
    """
    检查服务健康状态，包括 HTTP 引擎和代理池信息。
    """
    from utils.http_client import ENGINE_NAME
    from utils.proxy_pool import proxy_pool

    return {
        "status": "healthy",
        "version": "1.0.0",
        "framework": "FastAPI",
        "http_engine": ENGINE_NAME,
        "proxy_pool": proxy_pool.get_status(),
    }
