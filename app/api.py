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

from fastapi import APIRouter, UploadFile, File, Form, Request, Depends, Response, HTTPException, Query, Security
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from urllib.parse import quote

# ========== 内部模块导入 ==========
# 数据模型
from app.models import (
    UploadResponse,
    TimeLimit,
    ConfigUpdateRequest,
)
# 业务逻辑
from app.services import (
    process_file_upload,
    retrieve_file_content,
    get_file_list,
    get_file_detail,
    delete_file,
    batch_delete_files,
    get_storage_stats,
    get_upload_trend,
    get_expiring_files,
    manual_cleanup,
    get_prometheus_metrics,
)
# 安全模块
from app.core.security import limiter, verify_api_key
# 应用配置
from app.core.config import Config
# 配置管理
from app.core.config_manager import ConfigManager, CATEGORIES
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
    _: bool = Security(verify_api_key),         # 鉴权检查
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
    file_id: str        # 文件 ID (16 位十六进制)
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
    # 兼容带后缀的链接 (/f/xxx.json)，文件 ID 为纯十六进制不含点号
    file_id = file_id.split(".")[0]
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
            # RFC 5987 编码: 非 ASCII 文件名直接进 latin-1 头会抛 UnicodeEncodeError
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(filename)}",
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
            "status": "🟢 健康",
            "version": "1.0.0",
            "components": {
                "database": "🟢 正常",
                "encryption": "🔴 未启用",
                "compression": "🔴 未启用",
                "oss": "🟢 已启用",
                "redis": "🔴 未启用"
            }
        }
        ```
    """

    # ========== 检查数据库连接 ==========
    db_status = "🟢 正常"
    try:
        conn = await get_db_connection()
        await conn.execute("SELECT 1")
        await conn.close()
    except Exception as e:
        # 记录详细错误到日志
        log.error(f"数据库健康检查失败: {e}")
        # 返回脱敏的错误信息
        db_status = "🔴 异常"

    # ========== 检查加密引擎 ==========
    if Config.encryption_enabled:
        from app.core.crypto import CryptoEngine
        crypto_status = "🟢 已启用" if CryptoEngine.is_enabled() else "🔴 异常"
    else:
        crypto_status = "🔴 未启用"

    # ========== 检查压缩 ==========
    compression_status = "🟢 已启用" if Config.compression_enabled else "🔴 未启用"

    # ========== 检查 OSS ==========
    if Config.enable_oss:
        from app.core.oss_client import OSSClient
        oss_status = "🟢 已启用" if OSSClient.is_enabled() else "🔴 异常"
    else:
        oss_status = "🔴 未启用"

    # ========== 检查 Redis ==========
    redis_status = "🟢 已连接" if Config.redis_url else "🔴 未启用"

    # ========== 汇总状态 ==========
    # 只有 "异常" 状态才算异常，"未启用" 是正常状态
    all_components = [db_status, crypto_status, compression_status, oss_status, redis_status]
    overall_status = "🟢 健康" if all("异常" not in s for s in all_components) else "🟡 降级"

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


# 管理端点统一鉴权 (AUTH_ENABLED=false 时 verify_api_key 直接放行)
admin_router = APIRouter(
    prefix="/admin",
    dependencies=[Security(verify_api_key)],
    tags=["Admin"],
)


# ==========================================
# 📊 管理员统计接口
# ==========================================

@admin_router.get("/stats",
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
            "auth": Config.auth_enabled,
            "encryption": Config.encryption_enabled,
            "compression": Config.compression_enabled,
            "oss": Config.enable_oss,
            "redis": bool(Config.redis_url)
        }
    }


# ==========================================
# 📋 管理后台 API
# ==========================================

class BatchDeleteRequest(BaseModel):
    """批量删除请求"""
    file_ids: List[str]


@admin_router.get("/files", summary="文件列表", description="获取文件列表（分页、搜索、排序）")
async def admin_files_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    search: str = Query("", description="搜索关键词"),
    sort: str = Query("created_at", pattern="^(created_at|expire_at|filename|file_hash|id)$", description="排序字段"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="排序方向")
):
    """获取文件列表"""
    return await get_file_list(page, page_size, search, sort, order)


@admin_router.get("/files/{file_id}", summary="文件详情", description="获取文件详细信息")
async def admin_file_detail(file_id: str):
    """获取文件详情"""
    result = await get_file_detail(file_id)
    if not result:
        raise HTTPException(status_code=404, detail="文件不存在")
    return result


@admin_router.delete("/files/{file_id}", summary="删除文件", description="删除指定文件")
async def admin_delete_file(file_id: str):
    """删除文件"""
    result = await delete_file(file_id)
    if not result:
        raise HTTPException(status_code=404, detail="文件不存在")
    return {"message": "删除成功"}


@admin_router.delete("/files/batch", summary="批量删除", description="批量删除文件")
async def admin_batch_delete(request: BatchDeleteRequest):
    """批量删除文件"""
    result = await batch_delete_files(request.file_ids)
    return result


@admin_router.get("/stats/storage", summary="存储统计", description="获取存储使用统计")
async def admin_storage_stats():
    """获取存储统计"""
    return await get_storage_stats()


@admin_router.get("/stats/trend", summary="上传趋势", description="获取上传趋势数据")
async def admin_upload_trend(days: int = Query(30, ge=1, le=90, description="统计天数")):
    """获取上传趋势"""
    return await get_upload_trend(days)


@admin_router.get("/stats/expiring", summary="即将过期", description="获取即将过期的文件")
async def admin_expiring_files(days: int = Query(7, ge=1, le=30, description="天数范围")):
    """获取即将过期的文件"""
    return await get_expiring_files(days)


@admin_router.post("/cleanup", summary="清理过期", description="手动清理过期文件")
async def admin_cleanup():
    """手动清理过期文件"""
    return await manual_cleanup()


# ==========================================
# ⚙️ 配置管理 API
# ==========================================

@admin_router.get("/config", summary="获取配置", description="获取系统所有配置项")
async def admin_get_config():
    """
    ⚙️ 获取系统配置

    返回所有可配置的配置项及其当前值

    Returns:
        ConfigListResponse: 按分类组织的配置项列表
    """
    manager = ConfigManager()
    items = manager.get_config_items()

    # 按分类组织
    category_items: dict[str, list] = {cat: [] for cat in CATEGORIES}
    for item in items:
        if item.category not in category_items:
            category_items[item.category] = []
        category_items[item.category].append(item.model_dump())

    from app.models import ConfigCategory
    categories = [
        ConfigCategory(name=cat, items=category_items.get(cat, []))
        for cat in CATEGORIES
        if category_items.get(cat)
    ]

    return {
        "categories": [c.model_dump() for c in categories],
        "categories_order": CATEGORIES,
    }


@admin_router.post("/config/generate/{key_type}", summary="生成密钥", description="生成指定类型的密钥")
async def admin_generate_key(key_type: str):
    """
    🔑 生成密钥

    根据类型生成对应的密钥值

    Args:
        key_type: 密钥类型 (api_key, encryption_key)

    Returns:
        dict: 包含生成的密钥值
    """
    import secrets
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        Fernet = None

    if key_type == "api_key":
        # 生成随机 API Key
        generated_key = secrets.token_urlsafe(32)
        return {"key": generated_key}
    elif key_type == "encryption_key":
        # 生成 Fernet 加密密钥
        if Fernet is None:
            return {"error": "cryptography 库未安装"}
        generated_key = Fernet.generate_key().decode()
        return {"key": generated_key}
    else:
        return {"error": f"不支持的密钥类型: {key_type}"}


@admin_router.post("/config", summary="更新配置", description="更新系统配置并自动重启服务")
async def admin_update_config(request: ConfigUpdateRequest):
    """
    ⚙️ 更新系统配置

    更新配置项并写入 .env 文件，然后自动重启服务使配置生效

    Args:
        request: 包含更新配置的请求体

    Returns:
        ConfigUpdateResponse: 更新结果和重启状态
    """
    from app.models import ConfigUpdateResponse

    manager = ConfigManager()

    # 更新配置
    success, message = manager.update_config(request.updates)

    if not success:
        return ConfigUpdateResponse(success=False, message=message, restarting=False)

    # 重启服务
    restart_success, restart_message = manager.restart_service()

    return ConfigUpdateResponse(
        success=True,
        message=f"{message}，{restart_message}",
        restarting=restart_success
    )


# ==========================================
# 📊 监控指标 API
# ==========================================

@admin_router.get("/metrics", summary="监控指标", description="获取 Prometheus 监控指标（JSON 格式）")
async def admin_get_metrics():
    """
    📊 获取监控指标

    返回解析后的 Prometheus 指标数据，包括：
    - requests: 请求统计（总数、QPS、按方法/路径分组）
    - latency: 延迟统计（p50/p90/p95/p99 平均）
    - errors: 错误统计（总数、错误率、按状态码分组）
    - system: 系统指标（运行时长、内存使用、CPU 使用率）

    Returns:
        dict: 包含各类监控指标的字典

    返回格式:
        ```json
        {
            "requests": {
                "total": 1234,
                "qps": 0.12,
                "by_method": {"GET": 1000, "POST": 200},
                "by_path": {"/upload": 500, "/f/": 700}
            },
            "latency": {
                "p50": 50,
                "p90": 120,
                "p95": 180,
                "p99": 300,
                "avg": 80
            },
            "errors": {
                "total": 10,
                "rate": 0.81,
                "by_status": {"404": 5, "500": 3}
            },
            "system": {
                "uptime": 3600,
                "memory_usage": 128.5,
                "cpu_usage": 5.2
            }
        }
        ```
    """
    metrics = await get_prometheus_metrics()
    return {
        "code": 200,
        "msg": "✅ 获取成功",
        "data": metrics
    }


# ==========================================
# 📤 导出路由器
# ==========================================

router.include_router(admin_router)

__all__ = ["router"]
