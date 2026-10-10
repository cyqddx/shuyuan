"""
=============================================
🧪 加密模块测试
=============================================
"""

import pytest
from cryptography.fernet import Fernet

from app.core.crypto import CryptoEngine
from app.core.config import Config


@pytest.fixture
def enable_encryption(monkeypatch):
    """临时开启加密并注入测试密钥 (CryptoEngine 读全局 Config)"""
    test_key = Fernet.generate_key().decode()
    monkeypatch.setattr(Config, "encryption_enabled", True)
    monkeypatch.setattr(Config, "encryption_key", test_key)
    CryptoEngine.init_engine()
    return test_key


class TestCryptoEngine:
    """加密引擎测试"""

    def test_encrypt_decrypt_roundtrip(self, enable_encryption):
        """测试加密解密往返"""
        original = b"Hello, World!"
        encrypted = CryptoEngine.encrypt(original)
        decrypted = CryptoEngine.decrypt(encrypted)

        assert decrypted == original
        assert encrypted != original

    def test_disabled_encryption(self, monkeypatch):
        """测试禁用加密时数据不变"""
        monkeypatch.setattr(Config, "encryption_enabled", False)
        monkeypatch.setattr(Config, "encryption_key", "")
        CryptoEngine.init_engine()

        original = b"Hello, World!"
        assert CryptoEngine.encrypt(original) == original
        assert CryptoEngine.decrypt(original) == original

    def test_invalid_decryption(self, enable_encryption):
        """测试解密无效数据"""
        with pytest.raises(Exception):
            CryptoEngine.decrypt(b"invalid_encrypted_data")

    def test_is_enabled(self, enable_encryption, monkeypatch):
        """测试 is_enabled 方法"""
        assert CryptoEngine.is_enabled() is True

        monkeypatch.setattr(Config, "encryption_enabled", False)
        CryptoEngine.init_engine()
        assert CryptoEngine.is_enabled() is False
