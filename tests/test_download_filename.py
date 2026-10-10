"""
=============================================
🧪 文件下载接口测试
=============================================
覆盖回归: 中文文件名的 Content-Disposition 必须 RFC 5987 编码，
否则 Starlette latin-1 头编码抛 UnicodeEncodeError 导致 500
"""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch
from fastapi import FastAPI

from app.api import router
from app.core.security import limiter

app = FastAPI()
app.state.limiter = limiter
app.include_router(router)


CONTENT = '{"bookSourceName":"中文书源"}'.encode()  # 响应体；中文在 str 里再编码


async def _fake_retrieve(file_id: str):
    assert file_id == "0a1b2c3d4e5f6071"  # 后缀应被剥离
    return CONTENT, "中文名书源.json"


@pytest.mark.asyncio
async def test_download_chinese_filename():
    """中文文件名下载返回 200 且文件名 RFC 5987 编码"""
    with patch("app.api.retrieve_file_content", new=_fake_retrieve):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.get("/f/0a1b2c3d4e5f6071.json")
    assert r.status_code == 200
    assert "filename*=UTF-8''" in r.headers["content-disposition"]
    assert r.content == CONTENT


@pytest.mark.asyncio
async def test_download_legacy_no_suffix():
    """旧式无后缀链接保持兼容"""
    with patch("app.api.retrieve_file_content", new=_fake_retrieve):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.get("/f/0a1b2c3d4e5f6071")
    assert r.status_code == 200
