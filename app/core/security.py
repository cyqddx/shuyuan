"""
=============================================
🔐 安全与鉴权模块
=============================================
模块名称: security.py
模块功能:
    - API Key 鉴权
    - 请求频率限制 (基于 IP)
    - 支持 Redis 分布式限流
鉴权流程:
    - 从请求头提取 x-api-key
    - 与配置的 API_KEY 比对
    - 鉴权失败返回 401
限流机制:
    - 使用 slowapi 库
    - 支持 Redis 分布式或内存限流

"""

from fastapi import Request, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address

# ========== 内部模块导入 ==========
from app.core.config import Config
from app.core.logger import log


# ==========================================
# 🚦 限流器配置
# ==========================================

# 动态选择限流存储后端
# - 如果配置了 redis_url，使用 Redis (支持分布式)
# - 否则使用内存 (单机模式)
storage_uri = Config.redis_url if Config.redis_url else "memory://"

limiter = Limiter(
    key_func=get_remote_address,  # 使用 IP 地址作为限流键
    storage_uri=storage_uri,       # 存储后端
    default_limits=[Config.rate_limit]  # 默认限流规则
)

# 记录限流器状态
if Config.redis_url:
    log.info(f"🚦 限流器: Redis 分布式模式 ({Config.redis_url})")
else:
    log.info(f"🚦 限流器: 内存模式 (规则: {Config.rate_limit})")


# ==========================================
# 🔑 API Key 鉴权
# ==========================================

# 定义 API Key 提取器
# 从请求头 "x-api-key" 中提取 API Key
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)) -> bool:
    """
    🔑 验证 API Key

    根据配置决定是否进行鉴权:
        - 如果 AUTH_ENABLED=False，直接放行
        - 如果 AUTH_ENABLED=True，验证 API Key 是否匹配

    Args:
        api_key: 从请求头提取的 API Key

    Returns:
        bool: 验证成功返回 True

    Raises:
        HTTPException: 鉴权失败时抛出 401 错误

    注意:
        - auto_error=False 使得无 API Key 时不自动报错
        - 我们手动判断是否需要鉴权
    """

    # ========== 检查鉴权开关 ==========
    if not Config.auth_enabled:
        # 鉴权未开启，直接放行
        return True

    # ========== 验证 API Key ==========
    if api_key == Config.api_key:
        # API Key 匹配，验证通过
        return True

    # ========== 鉴权失败 ==========
    log.warning("⛔ 鉴权失败: 提供了无效的 API Key")

    raise HTTPException(
        status_code=401,
        detail="⛔ API Key 无效，请检查请求头中的 x-api-key",
        headers={"WWW-Authenticate": "ApiKey"}
    )


# ==========================================
# 📤 导出对象
# ==========================================

__all__ = [
    "limiter",          # 限流器实例
    "verify_api_key",   # API Key 验证函数
]
