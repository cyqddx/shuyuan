"""
=============================================
🧪 加密模块测试
=============================================
"""

import os

import pytest

from app.core.crypto import CryptoEngine
from app.core.config import Settings


class TestCryptoEngine:
    """加密引擎测试"""

    def test_encrypt_decrypt_roundtrip(self):
        """测试加密解密往返"""
        # 生成测试密钥
        from cryptography.fernet import Fernet
        test_key = Fernet.generate_key().decode()

        # 使用环境变量设置配置（pydantic 需要 lowercase boolean）
        os.environ["ENCRYPTION_ENABLED"] = "true"
        os.environ["ENCRYPTION_KEY"] = test_key

        # 重新加载配置
        config = Settings()
        CryptoEngine.init_engine()

        original = b"Hello, World!"
        encrypted = CryptoEngine.encrypt(original)
        decrypted = CryptoEngine.decrypt(encrypted)

        assert decrypted == original
        assert encrypted != original

    def test_disabled_encryption(self):
        """测试禁用加密时数据不变"""
        os.environ["ENCRYPTION_ENABLED"] = "false"
        os.environ["ENCRYPTION_KEY"] = ""

        config = Settings()
        CryptoEngine.init_engine()

        original = b"Hello, World!"
        encrypted = CryptoEngine.encrypt(original)
        decrypted = CryptoEngine.decrypt(encrypted)

        assert encrypted == original
        assert decrypted == original

    def test_invalid_decryption(self):
        """测试解密无效数据"""
        from cryptography.fernet import Fernet
        test_key = Fernet.generate_key().decode()

        os.environ["ENCRYPTION_ENABLED"] = "true"
        os.environ["ENCRYPTION_KEY"] = test_key

        config = Settings()
        CryptoEngine.init_engine()

        with pytest.raises(Exception):
            CryptoEngine.decrypt(b"invalid_encrypted_data")

    def test_is_enabled(self):
        """测试 is_enabled 方法"""
        from cryptography.fernet import Fernet
        test_key = Fernet.generate_key().decode()

        os.environ["ENCRYPTION_ENABLED"] = "true"
        os.environ["ENCRYPTION_KEY"] = test_key

        config = Settings()
        CryptoEngine.init_engine()
        assert CryptoEngine.is_enabled() is True

        os.environ["ENCRYPTION_ENABLED"] = "false"
        config = Settings()
        CryptoEngine.init_engine()
        assert CryptoEngine.is_enabled() is False
