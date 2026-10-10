"""
=============================================
🧪 安全模块测试
=============================================
"""

import pytest
from fastapi import HTTPException

from app.core.security import verify_api_key
from app.core.config import Config


class TestAPIKeyVerification:
    """API Key 验证测试"""

    @pytest.mark.asyncio
    async def test_valid_api_key(self, monkeypatch):
        """测试有效的 API Key"""
        monkeypatch.setattr(Config, "auth_enabled", True)
        monkeypatch.setattr(Config, "api_key", "test_secret_key_123")

        result = await verify_api_key("test_secret_key_123")
        assert result is True

    @pytest.mark.asyncio
    async def test_multiple_api_keys(self, monkeypatch):
        """API_KEYS 多钥匙: 任一命中通过"""
        monkeypatch.setattr(Config, "auth_enabled", True)
        monkeypatch.setattr(Config, "api_keys", "key-one, key-two")

        assert await verify_api_key("key-two") is True
        with pytest.raises(HTTPException):
            await verify_api_key("key-three")

    @pytest.mark.asyncio
    async def test_api_keys_fallback_single(self, monkeypatch):
        """API_KEYS 为空时回退单个 API_KEY"""
        monkeypatch.setattr(Config, "auth_enabled", True)
        monkeypatch.setattr(Config, "api_keys", "")
        monkeypatch.setattr(Config, "api_key", "only-key")

        assert await verify_api_key("only-key") is True

    @pytest.mark.asyncio
    async def test_invalid_api_key(self, monkeypatch):
        """测试无效的 API Key"""
        monkeypatch.setattr(Config, "auth_enabled", True)
        monkeypatch.setattr(Config, "api_key", "correct_key")

        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key("wrong_key")

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_auth_disabled(self, monkeypatch):
        """测试鉴权禁用时任何 Key 都通过"""
        monkeypatch.setattr(Config, "auth_enabled", False)

        result = await verify_api_key("any_key")
        assert result is True

    @pytest.mark.asyncio
    async def test_none_api_key_with_auth(self, monkeypatch):
        """测试未提供 API Key"""
        monkeypatch.setattr(Config, "auth_enabled", True)

        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(None)

        assert exc_info.value.status_code == 401
