"""
=============================================
🌐 HTTP 客户端模块
=============================================
模块名称: http_client.py
模块功能:
    - 全局 HTTPX 异步客户端单例
    - 复用 TCP 连接，提高性能
    - 连接池管理
使用场景:
    - OSS 文件上传 (可选)
    - 外部 API 调用

"""

import httpx
from typing import Optional

# 日志模块
from app.core.logger import log


# ==========================================
# 🌐 HTTP 客户端包装类
# ==========================================

class HTTPClientWrapper:
    """
    🌐 全局 HTTPX 异步客户端包装类

    功能:
        - 管理全局唯一的 HTTPX 异步客户端实例
        - 复用 TCP 连接，减少握手开销
        - 连接池管理，控制最大连接数

    属性:
        client (httpx.AsyncClient | None): HTTPX 异步客户端实例

    使用示例:
        ```python
        # 启动时初始化
        http_client.start()

        # 使用客户端
        client = http_client()
        response = await client.get("https://example.com")

        # 关闭时清理
        await http_client.stop()
        ```
    """

    # 类变量: HTTPX 客户端实例
    client: Optional[httpx.AsyncClient] = None

    def start(self):
        """
        🚀 启动 HTTP 客户端

        创建全局 HTTPX 异步客户端，配置连接池

        配置说明:
            - timeout: 请求超时时间 (30 秒)
            - max_keepalive_connections: 最大保持连接数 (20)
            - max_connections: 最大连接数 (100)

        注意:
            - 应在应用启动时调用一次
            - 重复调用会重新创建客户端
        """
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),  # 30 秒超时
            limits=httpx.Limits(
                max_keepalive_connections=20,  # 最大保持连接数
                max_connections=100            # 最大连接数
            ),
            # 自动跟随重定向
            follow_redirects=True
        )
        log.info("🌐 HTTPX 异步客户端: 已启动 (连接池: 20/100)")

    async def stop(self):
        """
    🛑 停止 HTTP 客户端

        关闭所有连接，释放资源

        注意:
            - 应在应用关闭时调用
            - 安全处理多次调用 (client 可能为 None)
        """
        if self.client:
            await self.client.aclose()
            self.client = None
            log.info("🌐 HTTPX 异步客户端: 已关闭")

    def __call__(self) -> httpx.AsyncClient:
        """
        🔙 获取 HTTP 客户端实例

        将包装类实例当作函数调用时，返回内部的 HTTPX 客户端

        Returns:
            httpx.AsyncClient: HTTPX 异步客户端实例

        Raises:
            RuntimeError: 客户端未初始化时抛出

        使用示例:
            ```python
            client = http_client()  # 获取客户端实例
            response = await client.get("https://example.com")
            ```
        """
        if self.client is None:
            raise RuntimeError("🌐 HTTP 客户端未初始化，请先调用 start() 方法")
        return self.client

    def is_started(self) -> bool:
        """
        🔍 检查客户端是否已启动

        Returns:
            bool: 客户端已启动返回 True
        """
        return self.client is not None


# ==========================================
# 🏷️ 全局 HTTP 客户端实例
# ==========================================

# 创建全局单例，供所有模块使用
http_client = HTTPClientWrapper()


# ==========================================
# 📤 导出实例
# ==========================================

__all__ = [
    "http_client",  # 全局 HTTP 客户端实例
]
