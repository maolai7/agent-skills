#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2026 tmwgsicp
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file in the project root for full license text.
# SPDX-License-Identifier: AGPL-3.0-only
"""
统计信息路由
"""

from fastapi import APIRouter
from pydantic import BaseModel
from utils.rate_limiter import rate_limiter

router = APIRouter()

class StatsResponse(BaseModel):
    """统计响应"""
    rate_limit: dict
    
    class Config:
        json_schema_extra = {
            "example": {
                "rate_limit": {
                    "global_requests": 5,
                    "global_limit": 10,
                    "active_ips": 2,
                    "article_requests": 3
                }
            }
        }

@router.get("/stats", response_model=StatsResponse, summary="获取API统计信息")
async def get_stats():
    """
    获取API统计信息
    
    包括:
    - 限频统计
    - 请求统计
    """
    return {
        "rate_limit": rate_limiter.get_stats()
    }

