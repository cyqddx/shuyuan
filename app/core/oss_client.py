"""
=============================================
☁️ 阿里云 OSS 存储客户端模块
=============================================
模块名称: oss_client.py
模块功能:
    - 封装阿里云 OSS SDK 操作
    - 提供异步文件上传/删除接口
    - 支持双写模式 (本地 + OSS)
依赖:
    - oss2: 阿里云 OSS Python SDK

"""

import asyncio
import oss2
from typing import Optional

# 应用配置
from app.core.config import Config
# 日志模块
from app.core.logger import log


class OSSClient:
    """
    ☁️ 阿里云 OSS 客户端

    功能:
        - 文件上传到 OSS
        - 从 OSS 删除文件
        - 自动处理异步调用

    属性:
        _auth (oss2.Auth | None): OSS 认证对象
        _bucket (oss2.Bucket | None): OSS Bucket 对象

    使用示例:
        ```python
        # 初始化 (应用启动时调用一次)
        OSSClient.init()

        # 上传文件
        url = await OSSClient.upload("file.bin", b"content")

        # 删除文件
        await OSSClient.delete("file.bin")
        ```
    """

    # 类变量: 认证和 Bucket 实例 (全局单例)
    _auth: Optional[oss2.Auth] = None
    _bucket: Optional[oss2.Bucket] = None

    @classmethod
    def init(cls):
        """
        🚀 初始化 OSS 客户端

        根据配置决定是否启用 OSS:
            - 如果 ENABLE_OSS=True，则初始化 OSS 客户端
            - 如果 ENABLE_OSS=False，则跳过初始化

        Raises:
            Exception: OSS 配置错误或连接失败时抛出

        注意:
            ⚠️ OSS 上传失败不会影响主流程，仍会使用本地存储
        """
        # 检查是否启用 OSS
        if not Config.enable_oss:
            cls._bucket = None
            log.info("☁️ OSS 客户端: 已禁用 (仅使用本地存储)")
            return

        # 检查 OSS 配置是否完整
        required_fields = ["endpoint", "bucket_name", "access_key", "secret_key"]
        missing = []

        for field in required_fields:
            if not Config.OSS_CONFIG.get(field):
                missing.append(field)

        if missing:
            log.warning(f"⚠️ OSS 配置不完整，缺失: {', '.join(missing)}，仅使用本地存储")
            cls._bucket = None
            return

        try:
            # 使用 AccessKey 和 SecretKey 初始化认证
            cls._auth = oss2.Auth(
                Config.OSS_CONFIG["access_key"],
                Config.OSS_CONFIG["secret_key"]
            )

            # 创建 Bucket 对象
            cls._bucket = oss2.Bucket(
                cls._auth,
                Config.OSS_CONFIG["endpoint"],
                Config.OSS_CONFIG["bucket_name"]
            )

            # 测试连接 (获取 Bucket 信息)
            cls._bucket.get_bucket_info()

            log.info(f"☁️ OSS 客户端: 已启用 (Bucket: {Config.OSS_CONFIG['bucket_name']})")

        except Exception as e:
            log.error(f"💥 OSS 客户端初始化失败: {e}")
            cls._bucket = None

    @classmethod
    async def upload(cls, filename: str, content: bytes) -> Optional[str]:
        """
    📤 上传文件到 OSS

        将文件内容上传到 OSS 存储桶

        Args:
            filename: 存储文件名 (如: "a1b2c3d4.bin")
            content: 文件内容 (字节数据)

        Returns:
            str | None: OSS 公网访问 URL，失败返回 None

        Raises:
            Exception: 上传失败时抛出 (由调用方处理)

        注意:
            - 使用 asyncio.to_thread 将同步 oss2 调用转为异步
            - 上传失败不会中断主流程，仅记录错误日志
        """
        # 检查 OSS 是否已初始化
        if cls._bucket is None:
            return None

        try:
            # 在线程池中执行同步的 oss2 上传操作
            # oss2.put_object 是同步方法，需要使用 to_thread 避免阻塞
            result = await asyncio.to_thread(
                cls._bucket.put_object,
                filename,      # OSS 中的文件名
                content        # 文件内容
            )

            # 检查上传结果
            if result.status == 200:
                # 上传成功，生成公网访问 URL
                url = f"{Config.OSS_CONFIG['base_url']}/{filename}"
                log.info(f"☁️ OSS 上传成功: {filename}")
                return url
            else:
                log.error(f"☁️ OSS 上传失败: HTTP {result.status}")
                return None

        except Exception as e:
            log.error(f"💥 OSS 上传异常: {filename} - {e}")
            return None

    @classmethod
    async def delete(cls, filename: str) -> bool:
        """
    🗑️ 从 OSS 删除文件

        从 OSS 存储桶中删除指定文件

        Args:
            filename: 要删除的文件名

        Returns:
            bool: 删除成功返回 True，失败返回 False

        注意:
            - 此方法主要用于后台清理任务
            - 删除失败不会中断清理流程，仅记录错误日志
        """
        # 检查 OSS 是否已初始化
        if cls._bucket is None:
            return False

        try:
            # 在线程池中执行同步的 oss2 删除操作
            result = await asyncio.to_thread(
                cls._bucket.delete_object,
                filename
            )

            # 检查删除结果
            if result.status == 204 or result.status == 200:
                log.info(f"☁️ OSS 删除成功: {filename}")
                return True
            else:
                log.warning(f"⚠️ OSS 删除失败: HTTP {result.status}")
                return False

        except Exception as e:
            log.error(f"💥 OSS 删除异常: {filename} - {e}")
            return False

    @classmethod
    async def delete_by_url(cls, url: str) -> bool:
        """
    🗑️ 从 OSS 删除文件 (通过 URL)

        从完整的 OSS URL 中提取文件名并删除

        Args:
            url: OSS 文件完整 URL

        Returns:
            bool: 删除成功返回 True，失败返回 False

        注意:
            - 从 URL 中提取文件名 (如: https://bucket.endpoint/filename.bin)
            - 主要用于后台清理任务清理 OSS 文件
        """
        try:
            # 从 URL 中提取文件名
            # URL 格式: https://bucket.oss-cn-hangzhou.aliyuncs.com/filename.bin
            filename = url.split("/")[-1]
            return await cls.delete(filename)
        except Exception as e:
            log.error(f"💥 解析 OSS URL 失败: {url} - {e}")
            return False

    @classmethod
    def is_enabled(cls) -> bool:
        """
        🔍 检查 OSS 是否启用

        Returns:
            bool: True 表示 OSS 已启用且配置正确，False 表示未启用
        """
        return cls._bucket is not None

    @classmethod
    def get_bucket_info(cls) -> dict:
        """
        📊 获取 Bucket 信息

        获取当前 OSS Bucket 的基本信息

        Returns:
            dict: Bucket 信息，包含名称、区域、创建时间等
                  未启用时返回空字典
        """
        if cls._bucket is None:
            return {}

        try:
            info = cls._bucket.get_bucket_info()
            return {
                "name": info.name,
                "location": info.location,
                "creation_date": info.creation_date,
                "storage_class": info.storage_class,
            }
        except Exception as e:
            log.error(f"💥 获取 Bucket 信息失败: {e}")
            return {}
