"""
=============================================
📦 数据模型模块
=============================================
模块名称: models.py
模块功能:
    - Pydantic 数据模型定义
    - API 请求/响应格式验证
    - 枚举类型定义
模型列表:
    - TimeLimit: 文件有效期枚举
    - FileData: 文件信息响应体
    - UploadResponse: 统一 API 响应格式

"""

from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, Any, List
from datetime import datetime


# ==========================================
# ⏰ 文件有效期枚举
# ==========================================

class TimeLimit(str, Enum):
    """
    ⏰ 文件有效期选项

    定义文件存储的有效期，用户上传时可选择

    选项:
        - ONE_DAY: 1 天后过期
        - SEVEN_DAYS: 7 天后过期
        - ONE_MONTH: 30 天后过期
        - PERMANENT: 永久存储

    使用示例:
        ```python
        # 表单提交
        time_limit: TimeLimit = Form(TimeLimit.PERMANENT)

        # 获取值
        if time_limit == TimeLimit.ONE_DAY:
            # 设置 1 天过期
        ```
    """

    # ========== 有效期选项 ==========
    ONE_DAY = "1d"         # 1 天
    SEVEN_DAYS = "7d"      # 7 天
    ONE_MONTH = "1m"       # 1 月 (按 30 天计算)
    PERMANENT = "perm"     # 永久

    @property
    def label(self) -> str:
        """
        📝 获取中文标签

        Returns:
            str: 有效期的中文描述
        """
        labels = {
            TimeLimit.ONE_DAY: "1 天",
            TimeLimit.SEVEN_DAYS: "7 天",
            TimeLimit.ONE_MONTH: "1 个月",
            TimeLimit.PERMANENT: "永久"
        }
        return labels.get(self, "未知")


# ==========================================
# 📄 文件信息响应体
# ==========================================

class FileData(BaseModel):
    """
    📄 文件信息响应体

    上传成功后返回的文件信息

    字段:
        - url: 文件访问地址
        - filename: 原始文件名
        - expiry: 过期时间 (或 "永久")
        - is_duplicate: 是否为秒传 (重复文件)
    """

    url: str = Field(
        ...,
        description="文件访问 URL"
    )

    filename: str = Field(
        ...,
        description="原始文件名"
    )

    expiry: str = Field(
        ...,
        description="过期时间或 '永久'"
    )

    is_duplicate: bool = Field(
        default=False,
        description="是否为重复文件 (秒传)"
    )


# ==========================================
# 📤 统一 API 响应格式
# ==========================================

class UploadResponse(BaseModel):
    """
    📤 统一 API 响应格式

    所有 API 接口返回的统一格式

    字段:
        - code: HTTP 状态码 (通常 200 表示成功)
        - msg: 响应消息 (中文描述)
        - data: 响应数据 (可选，根据接口不同)

    使用示例:
        ```python
        # 成功响应
        return {
            "code": 200,
            "msg": "✅ 上传成功",
            "data": {
                "url": "http://...",
                "filename": "config.json",
                "expiry": "永久",
                "is_duplicate": False
            }
        }

        # 错误响应
        return {
            "code": 400,
            "msg": "📄 JSON 格式无效",
            "data": None
        }
        ```
    """

    code: int = Field(
        ...,
        description="响应码 (200 表示成功，其他表示失败)"
    )

    msg: str = Field(
        ...,
        description="响应消息 (表情 + 中文)"
    )

    data: Optional[FileData] = Field(
        default=None,
        description="响应数据 (成功时包含，失败时为 None)"
    )


# ==========================================
# 📋 管理后台数据模型
# ==========================================

class FileListItem(BaseModel):
    """文件列表项"""

    id: str = Field(..., description="文件 ID")
    filename: str = Field(..., description="文件名")
    file_hash: str = Field(..., description="文件哈希")
    local_path: str = Field(..., description="本地路径")
    oss_path: Optional[str] = Field(None, description="OSS 路径")
    expire_at: Optional[datetime] = Field(None, description="过期时间")
    created_at: datetime = Field(..., description="创建时间")
    file_size: Optional[int] = Field(None, description="文件大小（字节）")
    is_expired: bool = Field(False, description="是否已过期")


class FileListResponse(BaseModel):
    """文件列表响应"""

    items: List[FileListItem] = Field(..., description="文件列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页大小")
    total_pages: int = Field(..., description="总页数")


class FileDetail(BaseModel):
    """文件详情"""

    id: str = Field(..., description="文件 ID")
    filename: str = Field(..., description="文件名")
    file_hash: str = Field(..., description="文件哈希")
    hash_algorithm: str = Field(..., description="哈希算法")
    local_path: str = Field(..., description="本地路径")
    oss_path: Optional[str] = Field(None, description="OSS 路径")
    expire_at: Optional[datetime] = Field(None, description="过期时间")
    created_at: datetime = Field(..., description="创建时间")
    file_size: int = Field(..., description="文件大小（字节）")
    content: Optional[str] = Field(None, description="文件内容（JSON）")


class StorageStats(BaseModel):
    """存储统计"""

    total_files: int = Field(..., description="文件总数")
    total_size: int = Field(..., description="总存储大小（字节）")
    by_type: dict = Field(..., description="按类型统计")
    by_expiry: dict = Field(..., description="按过期时间统计")
    expired_count: int = Field(..., description="已过期文件数")


class TrendItem(BaseModel):
    """趋势数据项"""

    date: str = Field(..., description="日期")
    count: int = Field(..., description="数量")
    size: int = Field(..., description="大小（字节）")


class TrendData(BaseModel):
    """趋势数据"""

    dates: List[str] = Field(..., description="日期列表")
    counts: List[int] = Field(..., description="数量列表")
    sizes: List[int] = Field(..., description="大小列表")


class ExpiringFile(BaseModel):
    """即将过期的文件"""

    id: str = Field(..., description="文件 ID")
    filename: str = Field(..., description="文件名")
    expire_at: datetime = Field(..., description="过期时间")
    days_until_expiry: int = Field(..., description="剩余天数")


class ExpiringData(BaseModel):
    """即将过期数据"""

    expiring_soon: int = Field(..., description="即将过期数量")
    files: List[ExpiringFile] = Field(..., description="即将过期的文件列表")


# ==========================================
# ⚙️ 配置管理模型
# ==========================================

class ConfigItem(BaseModel):
    """配置项"""
    key: str = Field(..., description="配置键名")
    label: str = Field(..., description="显示名称")
    value: str = Field(..., description="当前值")
    type: str = Field(default="text", description="输入类型: text, number, boolean, select")
    category: str = Field(default="基础", description="配置分类")
    description: str = Field(default="", description="配置说明")
    options: Optional[list[str]] = Field(None, description="可选值列表")
    sensitive: bool = Field(default=False, description="是否敏感信息")
    placeholder: str = Field(default="", description="占位符")
    min_value: Optional[int] = Field(None, description="最小值（数字类型）")
    max_value: Optional[int] = Field(None, description="最大值（数字类型）")
    required: bool = Field(default=False, description="是否必填")
    pattern: Optional[str] = Field(None, description="正则验证模式")
    generate_command: Optional[str] = Field(None, description="生成命令（用于密钥等）")
    generate_type: Optional[str] = Field(None, description="生成类型：api_key, encryption_key")


class ConfigCategory(BaseModel):
    """配置分类"""
    name: str = Field(..., description="分类名称")
    items: List[ConfigItem] = Field(..., description="配置项列表")


class ConfigListResponse(BaseModel):
    """配置列表响应"""
    categories: List[ConfigCategory] = Field(..., description="配置分类列表")
    categories_order: List[str] = Field(..., description="分类顺序")


class ConfigUpdateRequest(BaseModel):
    """配置更新请求"""
    updates: dict[str, str] = Field(..., description="配置更新 {key: value}")


class ConfigUpdateResponse(BaseModel):
    """配置更新响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    restarting: bool = Field(default=False, description="是否正在重启")


# ==========================================
# 📤 导出模型
# ==========================================

__all__ = [
    "TimeLimit",         # 文件有效期枚举
    "FileData",          # 文件信息响应体
    "UploadResponse",    # 统一 API 响应格式
    "FileListItem",      # 文件列表项
    "FileListResponse",  # 文件列表响应
    "FileDetail",        # 文件详情
    "StorageStats",      # 存储统计
    "TrendData",         # 趋势数据
    "ExpiringData",      # 即将过期数据
    "ConfigItem",        # 配置项
    "ConfigCategory",    # 配置分类
    "ConfigListResponse",  # 配置列表响应
    "ConfigUpdateRequest",  # 配置更新请求
    "ConfigUpdateResponse",  # 配置更新响应
]