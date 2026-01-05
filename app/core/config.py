"""
=============================================
⚙️ 应用配置模块
=============================================
模块名称: config.py
模块功能:
    - 从 .env 文件加载应用配置
    - 配置项验证和类型转换
    - 提供全局配置访问接口
配置原则:
    - 所有配置必须通过 .env 文件设置
    - 必填项缺失则服务无法启动
    - 使用 pydantic 进行类型验证

"""

import os
from pathlib import Path
from typing import Literal

# Pydantic 配置管理
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ========== 基础路径定义 ==========
# 项目根目录 (当前文件向上三级)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 数据库路径：优先使用环境变量，默认使用 data 目录（Docker 命名卷）
DB_PATH = Path(os.getenv("DB_PATH", PROJECT_ROOT / "data" / "files.db"))
# 本地存储目录
UPLOAD_DIR = PROJECT_ROOT / "uploads"
# 日志目录
LOG_DIR = PROJECT_ROOT / "logs"

# 确保 data 目录存在（如果使用本地路径）
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# 自动创建必要的目录
UPLOAD_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    """
    ⚙️ 应用配置类

    所有配置项从 .env 文件读取，使用 pydantic 进行验证

    配置项分类:
        - 基础配置: 服务域名、端口等
        - 鉴权配置: API Key、鉴权开关
        - 加密配置: 加密开关、密钥
        - 压缩配置: 压缩开关、压缩等级
        - OSS 配置: 阿里云 OSS 存储
        - 限流配置: 限流规则、Redis
        - 安全配置: 文件大小限制、CORS

    环境变量:
        自动从 .env 文件加载，变量名不区分大小写
    """

    # ==========================================
    # 🔧 Pydantic 配置
    # ==========================================

    model_config = SettingsConfigDict(
        env_file=".env",           # .env 文件路径
        env_file_encoding="utf-8", # 文件编码
        env_ignore_empty=True,     # 忽略空环境变量
        extra="ignore",            # 忽略未定义的环境变量
        case_sensitive=False,      # 不区分大小写
        populate_by_name=True,     # 允许通过别名访问
    )

    # ==========================================
    # 📍 基础配置 [必填]
    # ==========================================

    host_domain: str = Field(
        ...,
        alias="HOST_DOMAIN",
        description="服务对外域名/IP，用于生成直链"
    )

    # ==========================================
    # 🔐 鉴权配置 [可选]
    # ==========================================

    auth_enabled: bool = Field(
        default=False,
        alias="AUTH_ENABLED",
        description="是否开启 API Key 鉴权"
    )

    api_key: str = Field(
        default="secret",
        alias="API_KEY",
        description="API Key (开启鉴权时建议修改)"
    )

    # ==========================================
    # 🔒 加密配置 [可选]
    # ==========================================

    encryption_enabled: bool = Field(
        default=False,
        alias="ENCRYPTION_ENABLED",
        description="是否开启文件加密 (Fernet AES-128)"
    )

    encryption_key: str = Field(
        default="",
        alias="ENCRYPTION_KEY",
        description="Fernet 加密密钥 (开启加密时必填)"
    )

    # ==========================================
    # 🗜️ 压缩配置 [可选]
    # ==========================================

    compression_enabled: bool = Field(
        default=False,
        alias="COMPRESSION_ENABLED",
        description="是否开启 Gzip 压缩"
    )

    compression_level: int = Field(
        default=6,
        ge=1,
        le=9,
        alias="COMPRESSION_LEVEL",
        description="Gzip 压缩等级 (1-9，越高压缩率越高)"
    )

    # ==========================================
    # ☁️ OSS 云存储配置 [可选]
    # ==========================================

    enable_oss: bool = Field(
        default=False,
        alias="ENABLE_OSS",
        description="是否启用阿里云 OSS 存储"
    )

    oss_endpoint: str = Field(
        default="",
        alias="OSS_ENDPOINT",
        description="OSS Endpoint (如: oss-cn-hangzhou.aliyuncs.com)"
    )

    oss_bucket: str = Field(
        default="",
        alias="OSS_BUCKET",
        description="OSS Bucket 名称"
    )

    oss_ak: str = Field(
        default="",
        alias="OSS_AK",
        description="OSS AccessKey ID"
    )

    oss_sk: str = Field(
        default="",
        alias="OSS_SK",
        description="OSS AccessKey Secret"
    )

    oss_domain: str = Field(
        default="",
        alias="OSS_DOMAIN",
        description="OSS 公网访问域名 (如: https://bucket.oss-cn-hangzhou.aliyuncs.com)"
    )

    # ==========================================
    # 🚦 限流配置 [可选]
    # ==========================================

    rate_limit: str = Field(
        default="60/minute",
        alias="RATE_LIMIT",
        description="限流规则 (格式: 数量/时间单位，如: 60/minute, 10/second)"
    )

    redis_url: str = Field(
        default="",
        alias="REDIS_URL",
        description="Redis 连接地址 (留空使用内存限流)"
    )

    # ==========================================
    # 🛡️ 安全配置 [可选]
    # ==========================================

    max_file_size: int = Field(
        default=10485760,  # 10MB
        ge=1024,           # 最小 1KB
        alias="MAX_FILE_SIZE",
        description="文件大小限制 (字节)"
    )

    cors_origins: str = Field(
        default="*",
        alias="CORS_ORIGINS",
        description="CORS 允许的来源 (逗号分隔，* 表示全部)"
    )

    # ==========================================
    # 📂 文件类型限制
    # ==========================================

    # 允许的文件扩展名
    ALLOWED_EXTENSIONS: set = {".json"}

    # ==========================================
    # 🔗 大写属性别名 (兼容旧代码)
    # ==========================================
    # 这些属性提供大写访问方式，保持向后兼容

    @property
    def HOST_DOMAIN(self) -> str:
        return self.host_domain

    @property
    def AUTH_ENABLED(self) -> bool:
        return self.auth_enabled

    @property
    def API_KEY(self) -> str:
        return self.api_key

    @property
    def ENCRYPTION_ENABLED(self) -> bool:
        return self.encryption_enabled

    @property
    def ENCRYPTION_KEY(self) -> str:
        return self.encryption_key

    @property
    def COMPRESSION_ENABLED(self) -> bool:
        return self.compression_enabled

    @property
    def COMPRESSION_LEVEL(self) -> int:
        return self.compression_level

    @property
    def ENABLE_OSS(self) -> bool:
        return self.enable_oss

    @property
    def OSS_ENDPOINT(self) -> str:
        return self.oss_endpoint

    @property
    def OSS_BUCKET(self) -> str:
        return self.oss_bucket

    @property
    def OSS_AK(self) -> str:
        return self.oss_ak

    @property
    def OSS_SK(self) -> str:
        return self.oss_sk

    @property
    def OSS_DOMAIN(self) -> str:
        return self.oss_domain

    @property
    def RATE_LIMIT(self) -> str:
        return self.rate_limit

    @property
    def REDIS_URL(self) -> str:
        return self.redis_url

    @property
    def MAX_FILE_SIZE(self) -> int:
        return self.max_file_size

    @property
    def CORS_ORIGINS(self) -> list:
        return self._cors_origins_cached

    @property
    def DB_FILE(self) -> str:
        """数据库文件路径"""
        return str(DB_PATH)

    @property
    def UPLOAD_DIR(self) -> str:
        """上传目录路径"""
        return str(UPLOAD_DIR)

    @property
    def LOG_DIR(self) -> str:
        """日志目录路径"""
        return str(LOG_DIR)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 缓存 CORS_ORIGINS 列表
        self._cors_origins_cached = self._parse_cors_origins()

    def _parse_cors_origins(self) -> list:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    # ==========================================
    # 🧠 配置验证
    # ==========================================

    @model_validator(mode="after")
    def validate_encryption_config(self):
        """
        🔐 验证加密配置

        如果启用了加密，必须提供有效的密钥

        Raises:
            ValueError: 加密开启但密钥为空时抛出
        """
        if self.encryption_enabled and not self.encryption_key:
            raise ValueError(
                "💥 加密已开启 (ENCRYPTION_ENABLED=True) 但未设置 ENCRYPTION_KEY，"
                "服务无法启动。请先生成密钥: "
                "python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        return self

    @model_validator(mode="after")
    def validate_oss_config(self):
        """
        ☁️ 验证 OSS 配置

        如果启用了 OSS，必须提供完整的配置

        Raises:
            ValueError: OSS 配置不完整时记录警告 (不阻止启动)
        """
        if self.enable_oss:
            missing = []
            if not self.oss_endpoint:
                missing.append("OSS_ENDPOINT")
            if not self.oss_bucket:
                missing.append("OSS_BUCKET")
            if not self.oss_ak:
                missing.append("OSS_AK")
            if not self.oss_sk:
                missing.append("OSS_SK")
            if not self.oss_domain:
                missing.append("OSS_DOMAIN")

            if missing:
                # 记录警告但不阻止启动 (运行时会尝试使用本地存储)
                import warnings
                warnings.warn(
                    f"⚠️ OSS 配置不完整，缺失: {', '.join(missing)}，"
                    f"OSS 功能将不可用，仅使用本地存储"
                )
        return self

    # ==========================================
    # 🧩 辅助属性
    # ==========================================

    @property
    def OSS_CONFIG(self) -> dict:
        """
        ☁️ 获取 OSS 配置字典

        Returns:
            dict: OSS 配置字典，包含 endpoint, bucket_name, access_key, secret_key, base_url
        """
        return {
            "endpoint": self.oss_endpoint,
            "bucket_name": self.oss_bucket,
            "access_key": self.oss_ak,
            "secret_key": self.oss_sk,
            "base_url": self.oss_domain,
        }


# ==========================================
# 🏷️ 全局配置实例
# ==========================================

# 创建全局配置单例
# 应用启动时自动加载 .env 文件
try:
    Config = Settings()
except ValueError as e:
    # 配置验证失败，打印错误并退出
    print(f"\n{'='*60}")
    print(f"💥 配置错误，服务无法启动")
    print(f"{'='*60}")
    print(f"{e}")
    print(f"{'='*60}\n")
    raise
except Exception as e:
    # 其他配置加载错误
    print(f"\n{'='*60}")
    print(f"💥 配置加载失败")
    print(f"{'='*60}")
    print(f"{e}")
    print(f"{'='*60}\n")
    raise


# ==========================================
# 📤 导出配置
# ==========================================

__all__ = [
    "Config",           # 全局配置实例
    "Settings",         # 配置类 (用于类型注解)
    "PROJECT_ROOT",     # 项目根目录
    "UPLOAD_DIR",       # 上传目录
    "DB_PATH",          # 数据库文件路径
    "LOG_DIR",          # 日志目录
]
