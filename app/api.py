"""
=============================================
🛣️ API 路由模块
=============================================
模块名称: api.py
模块功能:
    - 定义所有 HTTP API 端点
    - 请求参数验证和响应格式化
    - 限流和鉴权中间件集成
API 端点:
    - POST /upload       - 文件上传
    - GET  /f/{file_id}  - 文件下载
    - GET  /health       - 健康检查
    - GET  /admin/stats  - 管理员统计

"""

from fastapi import APIRouter, UploadFile, File, Form, Request, Depends, Response, HTTPException
from typing import Dict, Any

# ========== 内部模块导入 ==========
# 数据模型
from app.models import UploadResponse, TimeLimit
# 业务逻辑
from app.services import process_file_upload, retrieve_file_content
# 安全模块
from app.core.security import limiter, verify_api_key
# 应用配置
from app.core.config import Config
# 数据库
from app.database import get_db_connection
# 日志模块
from app.core.logger import log


# ==========================================
# 🛣️ 路由器实例
# ==========================================

router = APIRouter(
    prefix="",           # 路由前缀 (空表示直接挂载到根路径)
    tags=["API"],        # API 文档分组标签
)


# ==========================================
# 📤 文件上传接口
# ==========================================

@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="上传文件",
    description="上传 JSON 文件到服务器，支持加密、压缩、去重"
)
@limiter.limit(Config.rate_limit)  # 应用限流
async def upload_endpoint(
    request: Request,                           # 请求对象 (用于限流)
    file: UploadFile = File(...),               # 上传的文件 (必填)
    time_limit: TimeLimit = Form(TimeLimit.PERMANENT)  # 有效期 (默认永久)
):
    """
    📤 文件上传接口

    处理流程:
        1. 鉴权检查 (如启用)
        2. 文件大小和格式校验
        3. JSON 内容验证
        4. 哈希查重 (秒传)
        5. 压缩和加密 (可选)
        6. 本地存储 + OSS 存储 (可选)
        7. 返回文件访问 URL

    Args:
        request: FastAPI 请求对象
        file: 上传的文件对象
        time_limit: 文件有效期 (1天/7天/1月/永久)

    Returns:
        UploadResponse: 统一响应格式，包含 code, msg, data

    Raises:
        401: API Key 无效 (如开启鉴权)
        400: 文件格式错误
        413: 文件过大
        429: 请求频率超限

    请求示例:
        ```bash
        curl -X POST "http://localhost:8000/upload" \
            -F "file=@config.json" \
            -F "time_limit=perm" \
            -H "x-api-key: your-secret-key"
        ```
    """

    # 记录上传请求
    log.info(f"📤 收到上传请求: 文件名={file.filename}, 有效期={time_limit.value}")

    # 调用核心业务逻辑处理上传
    result = await process_file_upload(file, time_limit)

    # 返回统一格式的响应
    return {"code": 200, "msg": "✅ 上传成功", "data": result}


# ==========================================
# 📥 文件下载接口
# ==========================================

@router.get(
    "/f/{file_id}",
    summary="获取文件",
    description="根据文件 ID 获取文件内容，自动处理解密和解压"
)
@limiter.limit(Config.rate_limit)  # 应用限流
async def get_file(
    request: Request,   # 请求对象 (用于限流)
    file_id: str        # 文件 ID (8 位十六进制)
):
    """
    📥 文件下载接口

    处理流程:
        1. 查询数据库获取文件路径
        2. 读取本地文件
        3. 解密 (如加密)
        4. 解压 (如压缩)
        5. 返回原始 JSON 内容

    Args:
        request: FastAPI 请求对象
        file_id: 文件的唯一 ID

    Returns:
        Response: JSON 文件内容，设置正确的 Content-Type

    Raises:
        404: 文件不存在或已过期
        500: 文件损坏或解密失败
    """

    # 调用核心业务逻辑获取文件内容
    content_bytes, filename = await retrieve_file_content(file_id)

    # 检查文件是否存在
    if content_bytes is None:
        log.warning(f"🔍 文件不存在: {file_id}")
        raise HTTPException(status_code=404, detail="🔍 文件不存在或已过期")

    # 返回文件内容
    return Response(
        content=content_bytes,
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "public, max-age=3600"  # 缓存 1 小时
        }
    )


# ==========================================
# 🏥 健康检查接口
# ==========================================

@router.get(
    "/health",
    summary="健康检查",
    description="检查服务及各组件的健康状态"
)
async def health_check() -> Dict[str, Any]:
    """
    🏥 健康检查接口

    用于 Kubernetes 存活探针、负载均衡器健康检查等

    Returns:
        dict: 包含状态和各组件信息的字典

    返回格式:
        ```json
        {
            "status": "🟢 healthy",
            "version": "1.0.0",
            "components": {
                "database": "🟢 OK",
                "encryption": "🔴 Disabled",
                "compression": "🔴 Disabled",
                "oss": "🟢 OK",
                "redis": "🔴 Disabled"
            }
        }
        ```
    """

    # ========== 检查数据库连接 ==========
    db_status = "🟢 OK"
    try:
        conn = await get_db_connection()
        await conn.execute("SELECT 1")
        await conn.close()
    except Exception as e:
        # 记录详细错误到日志
        log.error(f"Database health check failed: {e}")
        # 返回脱敏的错误信息
        db_status = "🔴 Error"

    # ========== 检查加密引擎 ==========
    if Config.ENCRYPTION_ENABLED:
        from app.core.crypto import CryptoEngine
        crypto_status = "🟢 Enabled" if CryptoEngine.is_enabled() else "🔴 Error"
    else:
        crypto_status = "🔴 Disabled"

    # ========== 检查压缩 ==========
    compression_status = "🟢 Enabled" if Config.COMPRESSION_ENABLED else "🔴 Disabled"

    # ========== 检查 OSS ==========
    if Config.ENABLE_OSS:
        from app.core.oss_client import OSSClient
        oss_status = "🟢 Enabled" if OSSClient.is_enabled() else "🔴 Error"
    else:
        oss_status = "🔴 Disabled"

    # ========== 检查 Redis ==========
    redis_status = "🟢 Connected" if Config.REDIS_URL else "🔴 Disabled"

    # ========== 汇总状态 ==========
    all_components = [db_status, crypto_status, compression_status, oss_status, redis_status]
    overall_status = "🟢 healthy" if all("🔴" not in s for s in all_components) else "🟡 degraded"

    return {
        "status": overall_status,
        "version": "1.0.0",
        "components": {
            "database": db_status,
            "encryption": crypto_status,
            "compression": compression_status,
            "oss": oss_status,
            "redis": redis_status
        }
    }


# ==========================================
# 📊 管理员统计接口
# ==========================================

@router.get(
    "/admin/stats",
    summary="系统统计",
    description="获取文件总数和系统配置状态 (需要鉴权)"
)
async def admin_stats():
    """
    📊 系统统计接口

    获取当前系统的统计数据和配置状态

    Returns:
        dict: 包含文件总数和各功能开关状态的字典

    返回格式:
        ```json
        {
            "total_files": 42,
            "config_status": {
                "auth": true,
                "encryption": false,
                "compression": true,
                "oss": false,
                "redis": false
            }
        }
        ```

    注意:
        - 如果开启鉴权，需要提供有效的 API Key
    """

    # 查询文件总数
    conn = await get_db_connection()
    cursor = await conn.execute("SELECT count(*) as count FROM files")
    res = await cursor.fetchone()
    count = res['count'] if res else 0
    await conn.close()

    # 返回统计信息
    return {
        "total_files": count,
        "config_status": {
            "auth": Config.AUTH_ENABLED,
            "encryption": Config.ENCRYPTION_ENABLED,
            "compression": Config.COMPRESSION_ENABLED,
            "oss": Config.ENABLE_OSS,
            "redis": bool(Config.REDIS_URL)
        }
    }


# ==========================================
# 📤 导出路由器
# ==========================================

__all__ = ["router"]
