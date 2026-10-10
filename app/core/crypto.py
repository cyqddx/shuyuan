"""
=============================================
🔐 加密引擎模块
=============================================
模块名称: crypto.py
模块功能:
    - 基于 Fernet (AES-128) 的对称加密/解密
    - 支持透明加解密 (根据配置自动开关)
    - 数据落盘前加密，读取时解密
加密算法:
    - Fernet (AES-128-CBC + HMAC)
    - 密钥长度: 32 字节 (URL-safe Base64 编码)

"""

# Fernet 加密实现 (基于 cryptography 库)
from cryptography.fernet import Fernet, InvalidToken

# 应用配置
from app.core.config import Config
# 日志模块
from app.core.logger import log


class CryptoEngine:
    """
    🔐 加密引擎

    功能:
        - 初始化时根据配置决定是否启用加密
        - 提供加密/解密接口，未启用时直接返回原数据
        - 所有加密操作在内存中进行，不产生临时文件

    属性:
        _cipher (Fernet | None): Fernet 加密器实例，未启用加密时为 None

    使用示例:
        ```python
        # 初始化 (应用启动时调用一次)
        CryptoEngine.init_engine()

        # 加密数据
        encrypted = CryptoEngine.encrypt(b"hello world")

        # 解密数据
        decrypted = CryptoEngine.decrypt(encrypted)
        ```
    """

    # 类变量: 加密器实例 (全局单例)
    _cipher: Fernet = None

    @classmethod
    def init_engine(cls):
        """
        🚀 初始化加密引擎

        根据配置决定是否启用加密:
            - 如果 ENCRYPTION_ENABLED=True，则初始化 Fernet 加密器
            - 如果 ENCRYPTION_ENABLED=False，则跳过初始化

        Raises:
            ValueError: 加密开启但密钥为空时抛出
            Exception: 密钥格式错误时抛出

        注意:
            ⚠️ 如果加密开启但初始化失败，服务必须停止运行
               防止敏感数据被明文存储
        """
        # 检查是否启用加密
        if Config.encryption_enabled:
            # 加密已开启，检查密钥是否配置
            if not Config.encryption_key:
                # 密钥缺失，抛出致命错误
                raise ValueError("💥 加密已开启 (ENCRYPTION_ENABLED=True) 但未设置 ENCRYPTION_KEY，服务停止")

            try:
                # 使用配置的密钥初始化 Fernet 加密器
                cls._cipher = Fernet(Config.encryption_key.encode())
                log.info("🔐 加密引擎: 已启用 (数据将以 AES-128 加密存储)")
            except Exception as e:
                # 密钥格式错误或其他初始化失败
                log.error(f"💥 加密引擎初始化失败: {e}")
                raise e
        else:
            # 加密未启用，直接返回原始数据
            cls._cipher = None
            log.info("🔓 加密引擎: 已禁用 (数据将以明文存储)")

    @classmethod
    def encrypt(cls, data: bytes) -> bytes:
        """
        🔒 加密数据

        如果加密已启用，使用 Fernet 加密数据
        如果加密未启用，直接返回原数据

        Args:
            data: 待加密的原始字节数据

        Returns:
            bytes: 加密后的数据 (未启用时返回原数据)

        注意:
            - Fernet 加密后会包含: 时间戳 + IV + HMAC + 密文
            - 加密后数据长度约为原数据长度的 1.5 倍
        """
        # 检查加密是否启用
        if not Config.encryption_enabled or cls._cipher is None:
            # 加密未启用，直接返回原数据
            return data

        # 使用 Fernet 加密数据
        # 加密过程: 生成时间戳 -> 生成 IV -> AES 加密 -> 计算 HMAC -> 拼接返回
        return cls._cipher.encrypt(data)

    @classmethod
    def decrypt(cls, data: bytes) -> bytes:
        """
        🔓 解密数据

        如果加密已启用，使用 Fernet 解密数据
        如果加密未启用，直接返回原数据

        Args:
            data: 待解密的字节数据

        Returns:
            bytes: 解密后的原始数据 (未启用时返回原数据)

        Raises:
            InvalidToken: 密钥错误或数据被篡改时抛出
            Exception: 解密失败时抛出

        注意:
            ⚠️ 如果数据被篡改或密钥错误，解密会失败并抛出 InvalidToken
        """
        # 检查加密是否启用
        if not Config.encryption_enabled or cls._cipher is None:
            # 加密未启用，直接返回原数据
            return data

        try:
            # 使用 Fernet 解密数据
            # 解密过程: 验证 HMAC -> 验证时间戳 -> 验证 IV -> AES 解密
            return cls._cipher.decrypt(data)
        except InvalidToken as e:
            # 密钥错误或数据被篡改
            log.error(f"💥 解密失败: 数据可能已损坏或密钥错误 - {e}")
            raise e
        except Exception as e:
            # 其他解密错误
            log.error(f"💥 解密失败: {e}")
            raise e

    @classmethod
    def is_enabled(cls) -> bool:
        """
        🔍 检查加密是否启用

        Returns:
            bool: True 表示加密已启用，False 表示未启用
        """
        return cls._cipher is not None
