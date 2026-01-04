"""
=============================================
⚠️ 自定义异常类模块
=============================================
模块名称: exceptions.py
模块功能:
    - 定义业务相关的自定义异常
    - 提供友好的错误提示 (表情+中文)
    - 统一错误码和错误信息格式
异常分类:
    - 文件相关: 文件过大、格式错误等
    - 鉴权相关: API Key 无效、权限不足等
    - 配置相关: 配置缺失、配置错误等
    - 存储相关: OSS 错误、存储空间不足等

"""

from fastapi import HTTPException
from typing import Any


# ==========================================
# 📦 文件相关异常
# ==========================================

class FileTooLargeError(HTTPException):
    """
    📦 文件过大异常

    当上传文件超过配置的大小限制时抛出

    Attributes:
        status_code: HTTP 状态码 (413 Payload Too Large)
        detail: 错误详情信息
    """

    def __init__(self, limit: int, actual: int = None):
        """
        初始化文件过大异常

        Args:
            limit: 允许的最大文件大小 (字节)
            actual: 实际文件大小 (字节)，可选
        """
        if actual:
            detail = f"📦 文件过大 ({actual} 字节)，限制为 {limit} 字节"
        else:
            detail = f"📦 文件过大，限制为 {limit} 字节"
        super().__init__(status_code=413, detail=detail)


class FileExtensionNotAllowedError(HTTPException):
    """
    🚫 文件扩展名不允许异常

    当上传文件的扩展名不在允许列表中时抛出

    Attributes:
        status_code: HTTP 状态码 (400 Bad Request)
        detail: 错误详情信息
    """

    def __init__(self, ext: str, allowed: set):
        """
        初始化扩展名不允许异常

        Args:
            ext: 实际的文件扩展名
            allowed: 允许的扩展名集合
        """
        allowed_list = ", ".join(allowed)
        detail = f"🚫 不允许的文件类型 ({ext})，仅支持: {allowed_list}"
        super().__init__(status_code=400, detail=detail)


class InvalidJSONError(HTTPException):
    """
    📄 JSON 格式无效异常

    当上传文件不是合法的 JSON 格式时抛出

    Attributes:
        status_code: HTTP 状态码 (400 Bad Request)
        detail: 错误详情信息
    """

    def __init__(self, original_error: str = None):
        """
        初始化 JSON 无效异常

        Args:
            original_error: 原始错误信息，可选
        """
        detail = "📄 JSON 格式无效，请检查文件内容"
        if original_error:
            detail = f"📄 JSON 格式无效: {original_error}"
        super().__init__(status_code=400, detail=detail)


class FileNotFoundError(HTTPException):
    """
    🔍 文件不存在异常

    当请求的文件 ID 不存在或已过期时抛出

    Attributes:
        status_code: HTTP 状态码 (404 Not Found)
        detail: 错误详情信息
    """

    def __init__(self, file_id: str = None):
        """
        初始化文件不存在异常

        Args:
            file_id: 文件 ID，可选
        """
        if file_id:
            detail = f"🔍 文件不存在或已过期: {file_id}"
        else:
            detail = "🔍 文件不存在或已过期"
        super().__init__(status_code=404, detail=detail)


class FileCorruptedError(HTTPException):
    """
    💥 文件损坏异常

    当文件读取失败、解密失败或解压失败时抛出

    Attributes:
        status_code: HTTP 状态码 (500 Internal Server Error)
        detail: 错误详情信息
    """

    def __init__(self, reason: str = None):
        """
        初始化文件损坏异常

        Args:
            reason: 损坏原因，可选
        """
        if reason:
            detail = f"💥 文件损坏或读取失败: {reason}"
        else:
            detail = "💥 文件损坏或读取失败"
        super().__init__(status_code=500, detail=detail)


# ==========================================
# 🔐 鉴权相关异常
# ==========================================

class InvalidAPIKeyError(HTTPException):
    """
    ⛔ API Key 无效异常

    当请求头中的 API Key 不正确时抛出

    Attributes:
        status_code: HTTP 状态码 (401 Unauthorized)
        detail: 错误详情信息
    """

    def __init__(self):
        """初始化 API Key 无效异常"""
        super().__init__(status_code=401, detail="⛔ API Key 无效或未提供")


class AuthenticationRequiredError(HTTPException):
    """
    🔒 需要鉴权异常

    当未开启鉴权但访问需要鉴权的接口时抛出

    Attributes:
        status_code: HTTP 状态码 (401 Unauthorized)
        detail: 错误详情信息
    """

    def __init__(self):
        """初始化需要鉴权异常"""
        super().__init__(status_code=401, detail="🔒 此接口需要鉴权访问")


# ==========================================
# ⚙️ 配置相关异常
# ==========================================

class ConfigurationError(Exception):
    """
    ⚙️ 配置错误异常

    当应用配置存在错误时抛出 (服务启动时检查)

    Attributes:
        message: 错误信息
    """

    def __init__(self, message: str):
        """
        初始化配置错误异常

        Args:
            message: 错误信息
        """
        self.message = f"⚙️ 配置错误: {message}"
        super().__init__(self.message)


class EncryptionKeyMissingError(ConfigurationError):
    """
    🔑 加密密钥缺失异常

    当开启加密但未设置密钥时抛出

    Attributes:
        message: 错误信息
    """

    def __init__(self):
        """初始化加密密钥缺失异常"""
        super().__init__("加密已开启但未设置 ENCRYPTION_KEY，请先生成密钥")


class OSSConfigurationError(ConfigurationError):
    """
    ☁️ OSS 配置错误异常

    当 OSS 配置不完整时抛出

    Attributes:
        message: 错误信息
    """

    def __init__(self, missing_fields: list = None):
        """
        初始化 OSS 配置错误异常

        Args:
            missing_fields: 缺失的配置字段列表
        """
        if missing_fields:
            fields = ", ".join(missing_fields)
            message = f"OSS 配置不完整，缺失: {fields}"
        else:
            message = "OSS 配置不完整"
        super().__init__(message)


# ==========================================
# ☁️ 存储相关异常
# ==========================================

class OSSUploadError(HTTPException):
    """
    ☁️ OSS 上传失败异常

    当 OSS 文件上传失败时抛出

    Attributes:
        status_code: HTTP 状态码 (500 Internal Server Error)
        detail: 错误详情信息
    """

    def __init__(self, reason: str = None):
        """
        初始化 OSS 上传失败异常

        Args:
            reason: 失败原因，可选
        """
        if reason:
            detail = f"☁️ OSS 上传失败: {reason}"
        else:
            detail = "☁️ OSS 上传失败"
        super().__init__(status_code=500, detail=detail)


class OSSDeleteError(Exception):
    """
    ☁️ OSS 删除失败异常

    当 OSS 文件删除失败时抛出 (后台任务)

    Attributes:
        message: 错误信息
    """

    def __init__(self, filename: str, reason: str = None):
        """
        初始化 OSS 删除失败异常

        Args:
            filename: 文件名
            reason: 失败原因，可选
        """
        if reason:
            self.message = f"☁️ OSS 删除失败 ({filename}): {reason}"
        else:
            self.message = f"☁️ OSS 删除失败: {filename}"
        super().__init__(self.message)


class StorageSpaceError(HTTPException):
    """
    💾 存储空间不足异常

    当本地磁盘空间不足时抛出

    Attributes:
        status_code: HTTP 状态码 (507 Insufficient Storage)
        detail: 错误详情信息
    """

    def __init__(self, free_space: int = None):
        """
        初始化存储空间不足异常

        Args:
            free_space: 剩余空间 (字节)，可选
        """
        if free_space:
            detail = f"💾 存储空间不足，剩余: {free_space} 字节"
        else:
            detail = "💾 存储空间不足，无法上传文件"
        super().__init__(status_code=507, detail=detail)


# ==========================================
# 🚦 限流相关异常
# ==========================================

class RateLimitExceededError(HTTPException):
    """
    🚦 请求频率超限异常

    当请求频率超过限制时抛出

    注意: 此异常由 slowapi 库自动处理，这里仅作类型定义

    Attributes:
        status_code: HTTP 状态码 (429 Too Many Requests)
        detail: 错误详情信息
    """

    def __init__(self, limit: str = None):
        """
        初始化请求频率超限异常

        Args:
            limit: 限流规则，如 "60/minute"
        """
        if limit:
            detail = f"🚦 请求频率过快，限制: {limit}"
        else:
            detail = "🚦 请求频率过快，请稍后再试"
        super().__init__(status_code=429, detail=detail)


# ==========================================
# 🔄 导出所有异常类
# ==========================================

__all__ = [
    # 文件相关
    "FileTooLargeError",
    "FileExtensionNotAllowedError",
    "InvalidJSONError",
    "FileNotFoundError",
    "FileCorruptedError",
    # 鉴权相关
    "InvalidAPIKeyError",
    "AuthenticationRequiredError",
    # 配置相关
    "ConfigurationError",
    "EncryptionKeyMissingError",
    "OSSConfigurationError",
    # 存储相关
    "OSSUploadError",
    "OSSDeleteError",
    "StorageSpaceError",
    # 限流相关
    "RateLimitExceededError",
]
