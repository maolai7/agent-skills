#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2026 tmwgsicp
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file in the project root for full license text.
# SPDX-License-Identifier: AGPL-3.0-only
"""
图片代理路由 - FastAPI版本
"""

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from urllib.parse import urlparse
import httpx

router = APIRouter()

ALLOWED_IMAGE_HOSTS = {
    "mmbiz.qpic.cn",
    "mmbiz.qlogo.cn",
    "wx.qlogo.cn",
    "res.wx.qq.com",
}

@router.get("/image", summary="图片代理下载")
async def proxy_image(url: str = Query(..., description="图片URL")):
    """
    代理下载微信图片，避免防盗链
    
    Args:
        url: 图片URL（仅允许微信CDN域名）
    
    Returns:
        图片数据流
    
    Raises:
        HTTPException: 当下载失败时
    """
    if not url:
        raise HTTPException(status_code=400, detail="URL参数不能为空")
    
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="仅支持HTTP/HTTPS协议")
    if parsed.hostname not in ALLOWED_IMAGE_HOSTS:
        raise HTTPException(status_code=403, detail="仅允许代理微信CDN图片")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            
            # 获取内容类型
            content_type = response.headers.get("content-type", "image/jpeg")
            
            # 返回图片流
            return StreamingResponse(
                iter([response.content]),
                media_type=content_type,
                headers={
                    "Content-Disposition": f"inline; filename={url.split('/')[-1]}"
                }
            )
    
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"下载图片失败: HTTP {e.response.status_code}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载图片失败: {str(e)}")
