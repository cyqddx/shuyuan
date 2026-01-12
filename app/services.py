"""
=============================================
⚙️ 核心业务逻辑模块
=============================================
模块名称: services.py
模块功能:
    - 文件上传处理: 校验 -> 查重 -> 压缩 -> 加密 -> 存储
    - 文件读取处理: 读取 -> 解密 -> 解压 -> 返回
    - 后台清理任务: 定期清理过期文件
    - TTL 缓存: 文件元数据缓存（5分钟过期）
数据处理流程:
    写入: 接收文件 -> JSON 校验 -> BLAKE2b 哈希 -> 去重检查 -> 压缩 -> 加密 -> 存储
    读取: 读取文件 -> 解密 -> 解压 -> 返回 JSON

使用的 Python 标准库模块:
    - pathlib.Path: 现代路径操作
    - secrets: 安全随机数生成（文件 ID）
    - hashlib.blake2b: 高速哈希计算
    - functools.cached_property: 延迟初始化（config.py）
    - contextlib.asynccontextmanager: 异步上下文管理（database.py）

"""

# ========== 标准库导入 ==========
import hashlib  # 哈希计算
import gzip  # Gzip 压缩
import secrets  # 安全随机数生成
import datetime  # 时间处理
import asyncio  # 异步任务
import re  # 正则表达式
import time  # 时间戳
import psutil  # 系统信息
from pathlib import Path  # 路径操作

# ========== 第三方库导入 ==========
import anyio  # 异步文件操作
import orjson  # 高性能 JSON 处理
from fastapi import UploadFile, HTTPException
from dataclasses import dataclass
from typing import Any
from cachetools import TTLCache  # TTL 缓存

# ========== 内部模块导入 ==========
from app.core.config import Config
from app.database import get_db_connection
from app.models import TimeLimit
from app.core.logger import log
from app.core.http_client import http_client
from app.core.crypto import CryptoEngine


# ==========================================
# ⚙️ JSON 验证配置
# ==========================================

@dataclass
class JSONValidationConfig:
    """JSON 验证配置类"""
    max_depth: int = 20        # 最大嵌套深度
    max_fields: int = 1000     # 最大字段/数组长度
    max_total_length: int = 10 * 1024 * 1024  # 最大总大小 (10MB)


def _validate_json_structure(obj: Any, depth: int = 0, config: JSONValidationConfig | None = None) -> None:
    """
    递归验证 JSON 结构

    防止深度嵌套攻击和超大对象攻击

    Args:
        obj: 待验证的 JSON 对象
        depth: 当前嵌套深度
        config: 验证配置

    Raises:
        HTTPException: 验证失败时抛出
    """
    if config is None:
        config = JSONValidationConfig()

    # 检查深度
    if depth > config.max_depth:
        raise HTTPException(
            status_code=400,
            detail=f"📄 JSON 嵌套过深（最大 {config.max_depth} 层）"
        )

    # 检查字段数量
    if isinstance(obj, dict):
        if len(obj) > config.max_fields:
            raise HTTPException(
                status_code=400,
                detail=f"📄 JSON 字段过多（最大 {config.max_fields} 个）"
            )
        for value in obj.values():
            _validate_json_structure(value, depth + 1, config)
    elif isinstance(obj, list):
        if len(obj) > config.max_fields:
            raise HTTPException(
                status_code=400,
                detail=f"📄 JSON 数组过长（最大 {config.max_fields} 个元素）"
            )
        for item in obj:
            _validate_json_structure(item, depth + 1, config)


# ==========================================
# 💾 TTL 缓存
# ==========================================

# 全局缓存：文件元数据（5分钟过期）
_metadata_cache: TTLCache = TTLCache(maxsize=2048, ttl=300)

# 全局缓存：哈希查重结果（1分钟过期）
_hash_cache: TTLCache = TTLCache(maxsize=4096, ttl=60)


def invalidate_file_cache(file_id: str) -> None:
    """
    🗑️ 清除文件缓存

    Args:
        file_id: 文件 ID
    """
    _metadata_cache.pop(file_id, None)


# ==========================================
# 🔧 工具函数
# ==========================================

def compress_data(data: bytes) -> bytes:
    """
    🗜️ 压缩数据

    使用 Gzip 算法压缩数据，节省存储空间和带宽

    Args:
        data: 待压缩的原始字节数据

    Returns:
        bytes: 压缩后的数据 (未启用压缩时返回原数据)

    注意:
        - 压缩等级由 COMPRESSION_LEVEL 控制 (1-9)
        - 典型 JSON 文件可压缩 60-80%
    """
    if Config.COMPRESSION_ENABLED:
        return gzip.compress(data, compresslevel=Config.COMPRESSION_LEVEL)
    return data


def decompress_data(data: bytes) -> bytes:
    """
    📦 解压数据

    使用 Gzip 算法解压数据

    Args:
        data: 待解压的字节数据

    Returns:
        bytes: 解压后的原始数据

    注意:
        - 自动检测数据是否为 Gzip 格式 (魔数: 0x1f 0x8b)
        - 非压缩数据直接返回原样
    """
    # 检查是否为 Gzip 格式 (魔数检测)
    if Config.COMPRESSION_ENABLED and data.startswith(b'\x1f\x8b'):
        return gzip.decompress(data)
    return data


def calculate_hash(content: bytes, use_blake2b: bool = True) -> tuple[str, str]:
    """
    🔐 计算数据哈希

    使用 blake2b 或 MD5 算法计算内容的哈希值，用于文件去重

    Args:
        content: 待计算的字节数据
        use_blake2b: 是否使用 blake2b（默认 True），False 则使用 MD5

    Returns:
        tuple[str, str]: (哈希值, 哈希算法标识 "blake2b" 或 "md5")

    注意:
        - blake2b 比 MD5 更快且更安全
        - digest_size=16 生成 128 位（32 位十六进制），与 MD5 长度相同
        - 相同内容必然产生相同哈希，实现"秒传"功能
    """
    if use_blake2b:
        # blake2b digest_size=16 生成 128 位（32 位十六进制），与 MD5 长度一致
        return hashlib.blake2b(content, digest_size=16).hexdigest(), "blake2b"
    else:
        return hashlib.md5(content).hexdigest(), "md5"


def validate_and_minify(content: bytes) -> bytes:
    """
    ✅ 校验并压缩 JSON

    使用 orjson 校验 JSON 格式，并去除多余空格

    Args:
        content: 待校验的 JSON 字节数据

    Returns:
        bytes: 压缩后的 JSON 字节数据 (无空格、无换行)

    Raises:
        HTTPException: JSON 格式无效、过大、嵌套过深时抛出 400 错误

    注意:
        - orjson 比 stdlib json 快 5-10 倍
        - 强制校验确保存储的都是合法 JSON
        - 验证深度、字段数量和总大小，防止恶意攻击
    """
    config = JSONValidationConfig()

    # 先检查总大小
    if len(content) > config.max_total_length:
        raise HTTPException(
            status_code=413,
            detail=f"📄 JSON 过大（最大 {config.max_total_length // 1024 // 1024} MB）"
        )

    try:
        # 解析 JSON (同时校验格式)
        obj = orjson.loads(content)

        # 验证 JSON 结构 (深度、字段数量)
        _validate_json_structure(obj, config=config)

        # 序列化回 JSON (去除空格和换行)
        return orjson.dumps(obj)

    except orjson.JSONDecodeError:
        # JSON 格式无效
        raise HTTPException(status_code=400, detail="📄 JSON 格式无效，请检查文件内容")
    except HTTPException:
        # 重新抛出我们的验证错误
        raise


def calculate_expiry(limit: TimeLimit) -> datetime.datetime | None:
    """
    📅 计算过期时间

    根据用户选择的有效期计算具体的过期时间点

    Args:
        limit: 有效期枚举 (1天/7天/1月/永久)

    Returns:
        datetime | None: 过期时间点，永久返回 None

    注意:
        - 时间从当前时刻开始计算
        - 1 月按 30 天计算
    """
    if limit == TimeLimit.PERMANENT:
        return None
    # 天数映射
    days_map = {
        TimeLimit.ONE_DAY: 1,
        TimeLimit.SEVEN_DAYS: 7,
        TimeLimit.ONE_MONTH: 30
    }
    return datetime.datetime.now() + datetime.timedelta(days=days_map.get(limit, 0))


# ==========================================
# 📤 文件上传处理
# ==========================================

async def process_file_upload(file: UploadFile, time_limit: TimeLimit):
    """
    📤 处理文件上传

    完整的上传处理流程:
        1. 文件大小检查
        2. 后缀名校验
        3. 读取并标准化 JSON
        4. 哈希查重 (秒传)
        5. 数据压缩 (可选)
        6. 数据加密 (可选)
        7. 本地存储
        8. OSS 存储 (可选)
        9. 写入元数据

    Args:
        file: 上传的文件对象
        time_limit: 文件有效期 (1天/7天/1月/永久)

    Returns:
        dict: 包含 url, filename, expiry, is_duplicate 的响应字典

    Raises:
        HTTPException: 文件过大、格式错误等异常
    """

    # ========== 1. 文件大小检查 ==========
    # 读取文件内容到内存 (小文件场景)
    raw_content = await file.read()

    file_size = len(raw_content)
    if file_size > Config.MAX_FILE_SIZE:
        log.warning(f"📦 文件过大: {file_size} 字节，限制: {Config.MAX_FILE_SIZE} 字节")
        raise HTTPException(
            status_code=413,
            detail=f"📦 文件过大，限制为 {Config.MAX_FILE_SIZE} 字节"
        )

    log.info(f"📦 接收文件: {file.filename} ({file_size} 字节)")

    # ========== 2. 后缀名校验 ==========
    ext = Path(file.filename).suffix.lower()
    if ext not in Config.ALLOWED_EXTENSIONS:
        log.warning(f"🚫 不允许的文件类型: {ext}")
        raise HTTPException(
            status_code=400,
            detail=f"🚫 不允许的文件类型，仅支持: {', '.join(Config.ALLOWED_EXTENSIONS)}"
        )

    # ========== 3. JSON 校验并标准化 ==========
    try:
        minified_content = validate_and_minify(raw_content)
        log.info(f"✅ JSON 校验通过，压缩后: {len(minified_content)} 字节")
    except HTTPException:
        raise

    # ========== 4. 哈希查重 ==========
    file_hash, hash_algorithm = calculate_hash(minified_content, use_blake2b=True)

    conn = await get_db_connection()
    # 查询是否存在相同哈希的文件（同时支持 blake2b 和 md5）
    cursor = await conn.execute("""
        SELECT id, oss_path FROM files
        WHERE (file_hash = ? AND hash_algorithm = 'blake2b')
           OR (file_hash = ? AND hash_algorithm = 'md5')
    """, (file_hash, file_hash))
    existing = await cursor.fetchone()

    if existing:
        # 命中缓存，直接返回现有链接 (秒传)
        log.info(f"✨ 检测到重复文件，使用秒传: {file_hash}")
        await conn.close()

        # 加密/压缩模式下统一返回 API 链接
        if Config.ENCRYPTION_ENABLED or Config.COMPRESSION_ENABLED:
            return_url = f"{Config.HOST_DOMAIN}/f/{existing['id']}"
        else:
            # 明文模式优先返回 OSS 链接
            return_url = existing['oss_path'] if existing['oss_path'] else f"{Config.HOST_DOMAIN}/f/{existing['id']}"

        return {
            "url": return_url,
            "filename": file.filename,
            "is_duplicate": True,
            "expiry": "永久"
        }

    # ========== 5. 数据处理 (压缩 -> 加密) ==========
    # 5.1 压缩 (可选)
    processed_content = compress_data(minified_content)
    if Config.COMPRESSION_ENABLED:
        compression_ratio = len(processed_content) / len(minified_content)
        log.info(f"🗜️ 压缩完成: 压缩率 {compression_ratio:.1%}")

    # 5.2 加密 (可选)
    final_content = CryptoEngine.encrypt(processed_content)

    # ========== 6. 文件存储 ==========
    # 生成唯一的文件 ID (8 位十六进制，使用安全的随机数)
    file_id = secrets.token_hex(4)

    # 确定存储文件名
    # 加密/压缩模式下使用 .bin 后缀，避免误导
    if Config.ENCRYPTION_ENABLED or Config.COMPRESSION_ENABLED:
        save_filename = f"{file_id}.bin"
    else:
        save_filename = f"{file_id}{ext}"

    # 6.1 本地存储
    local_path = Path(Config.UPLOAD_DIR) / save_filename
    async with await anyio.open_file(str(local_path), 'wb') as f:
        await f.write(final_content)
    log.info(f"💾 本地存储完成: {save_filename}")

    # 6.2 OSS 存储 (可选)
    oss_url = None
    if Config.ENABLE_OSS:
        # 使用 OSS 客户端上传
        from app.core.oss_client import OSSClient
        try:
            oss_url = await OSSClient.upload(save_filename, final_content)
            log.info(f"☁️ OSS 上传成功: {oss_url}")
        except Exception as e:
            log.error(f"☁️ OSS 上传失败: {e}")
            # OSS 上传失败不影响主流程，仍使用本地存储

    # ========== 7. 生成返回链接 ==========
    if Config.ENCRYPTION_ENABLED or Config.COMPRESSION_ENABLED:
        # 加密/压缩模式必须走 API 解密
        return_url = f"{Config.HOST_DOMAIN}/f/{file_id}"
    else:
        # 明文模式优先返回 OSS 链接
        return_url = oss_url if oss_url else f"{Config.HOST_DOMAIN}/f/{file_id}"

    # ========== 8. 写入元数据 ==========
    expire_at = calculate_expiry(time_limit)

    try:
        await conn.execute("""
            INSERT INTO files (id, file_hash, hash_algorithm, filename, local_path, oss_path, expire_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (file_id, file_hash, hash_algorithm, file.filename, save_filename, oss_url, expire_at))
        await conn.commit()
    except Exception as e:
        log.error(f"💥 数据库写入失败: {e}")
        raise e
    finally:
        await conn.close()

    log.info(f"✅ 上传成功: {file_id} -> {return_url}")

    return {
        "url": return_url,
        "filename": file.filename,
        "expiry": str(expire_at) if expire_at else "永久",
        "is_duplicate": False
    }


# ==========================================
# 📥 文件读取处理
# ==========================================

async def retrieve_file_content(file_id: str):
    """
    📥 获取文件内容

    完整的读取处理流程:
        1. 查询数据库获取文件路径
        2. 读取本地文件
        3. 解密 (如果加密)
        4. 解压 (如果压缩)
        5. 返回原始 JSON

    Args:
        file_id: 文件的唯一 ID

    Returns:
        tuple: (文件内容 bytes, 原始文件名 str)，不存在时返回 (None, None)

    Raises:
        HTTPException: 文件损坏、解密失败等异常
    """

    # ========== 1. 查询文件元数据 ==========
    # 先检查缓存
    cached_metadata = _metadata_cache.get(file_id)
    if cached_metadata:
        local_path = Path(Config.UPLOAD_DIR) / cached_metadata["local_path"]
        original_name = cached_metadata["filename"]
    else:
        conn = await get_db_connection()
        cursor = await conn.execute("SELECT local_path, filename FROM files WHERE id = ?", (file_id,))
        row = await cursor.fetchone()
        await conn.close()

        if not row:
            # 文件不存在
            log.warning(f"🔍 文件不存在: {file_id}")
            return None, None

        local_path = Path(Config.UPLOAD_DIR) / row['local_path']
        original_name = row['filename']
        # 写入缓存
        _metadata_cache[file_id] = {"local_path": row['local_path'], "filename": original_name}

    # ========== 2. 检查文件是否存在 ==========
    if not local_path.exists():
        log.warning(f"🔍 文件已丢失: {local_path}，清理数据库记录")
        # 文件丢失，清理数据库记录
        conn = await get_db_connection()
        await conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
        await conn.commit()
        await conn.close()
        invalidate_file_cache(file_id)
        return None, None

    # ========== 3. 读取文件内容 ==========
    try:
        async with await anyio.open_file(str(local_path), 'rb') as f:
            content = await f.read()
    except Exception as e:
        log.error(f"💥 文件读取失败 {file_id}: {e}")
        raise HTTPException(status_code=500, detail="📄 文件读取失败")

    # ========== 4. 逆向处理 (解密 -> 解压) ==========
    try:
        # 4.1 解密 (如果加密)
        decrypted = CryptoEngine.decrypt(content)

        # 4.2 解压 (如果压缩)
        final_json = decompress_data(decrypted)

        return final_json, original_name

    except Exception as e:
        log.error(f"❌ 文件处理失败 {file_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="📄 文件损坏或解密失败"
        )


# ==========================================
# 🧹 后台清理任务
# ==========================================

async def clean_expired_task():
    """
    🧹 后台清理过期文件任务（优化版）

    功能:
        - 定期扫描数据库中的过期文件
        - 批量删除本地文件
        - 批量删除 OSS 文件 (如果启用)
        - 批量删除数据库记录

    运行周期:
        - 每小时执行一次 (3600 秒)

    注意:
        - 这是一个无限循环的任务，在应用启动时创建
        - 异常会被捕获并记录，不会中断任务循环
        - 使用批量操作和并发处理提升性能
    """

    log.info("🧹 后台清理任务已启动，每小时执行一次")

    # 批量大小
    BATCH_SIZE = 100

    while True:
        try:
            # ========== 1. 分批查询过期文件 ==========
            conn = await get_db_connection()
            now = datetime.datetime.now()

            # 分批查询过期文件
            cursor = await conn.execute(
                "SELECT id, local_path, oss_path FROM files WHERE expire_at < ? LIMIT ?",
                (now, BATCH_SIZE)
            )
            rows = await cursor.fetchall()

            if not rows:
                await conn.close()
            else:
                log.info(f"🧹 发现 {len(rows)} 个过期文件需要清理")

                # ========== 2. 收集需要删除的文件信息 ==========
                to_delete_local = []
                to_delete_oss = []
                file_ids = []

                for row in rows:
                    file_ids.append(row['id'])
                    local_full = Path(Config.UPLOAD_DIR) / row['local_path']
                    to_delete_local.append(str(local_full))
                    if row['oss_path']:
                        to_delete_oss.append(row['oss_path'])

                # ========== 3. 并发删除本地文件 ==========
                async def delete_local(path: str):
                    path_obj = Path(path)
                    if path_obj.exists():
                        try:
                            await asyncio.to_thread(path_obj.unlink)
                            return path, True
                        except OSError as e:
                            log.error(f"⚠️ 删除本地文件失败 {path}: {e}")
                            return path, False
                    return path, False

                local_results = await asyncio.gather(
                    *[delete_local(p) for p in to_delete_local],
                    return_exceptions=True
                )

                deleted_count = sum(1 for r in local_results if isinstance(r, tuple) and r[1])
                log.info(f"🗑️ 清理任务: 已删除 {deleted_count}/{len(to_delete_local)} 个本地文件")

                # ========== 4. 批量删除 OSS 文件 ==========
                if to_delete_oss and Config.ENABLE_OSS:
                    from app.core.oss_client import OSSClient
                    for oss_url in to_delete_oss:
                        try:
                            await OSSClient.delete(oss_url)
                            log.info(f"☁️ 清理任务: 已删除 OSS 文件 {oss_url}")
                        except Exception as e:
                            log.error(f"⚠️ 删除 OSS 文件失败 {oss_url}: {e}")

                # ========== 5. 批量删除数据库记录（单次事务）==========
                placeholders = ','.join('?' * len(file_ids))
                await conn.execute(
                    f"DELETE FROM files WHERE id IN ({placeholders})",
                    file_ids
                )
                await conn.commit()
                await conn.close()

                # 清除缓存
                for file_id in file_ids:
                    invalidate_file_cache(file_id)

                log.info(f"✅ 清理任务完成，共清理 {len(file_ids)} 个文件")

                # ========== 6. 继续检查是否还有更多 ==========
                if len(rows) == BATCH_SIZE:
                    continue

        except Exception as e:
            # 捕获所有异常，防止任务循环中断
            log.error(f"🚨 清理任务严重错误: {e}")

        # ========== 7. 等待下次执行 ==========
        # 每小时执行一次 (3600 秒)
        await asyncio.sleep(3600)


# ==========================================
# 📋 管理后台业务逻辑
# ==========================================

async def get_file_list(
    page: int = 1,
    page_size: int = 20,
    search: str = "",
    sort: str = "created_at",
    order: str = "desc"
) -> dict:
    """
    📋 获取文件列表

    Args:
        page: 页码（从 1 开始）
        page_size: 每页大小
        search: 搜索关键词（文件名或 ID）
        sort: 排序字段
        order: 排序方向（asc/desc）

    Returns:
        dict: 包含 items, total, page, page_size, total_pages 的字典
    """
    conn = await get_db_connection()

    # 构建 WHERE 条件
    where_conditions = []
    params = []
    if search:
        where_conditions.append("(filename LIKE ? OR id LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

    # 获取总数
    count_query = f"SELECT COUNT(*) as count FROM files WHERE {where_clause}"
    cursor = await conn.execute(count_query, params)
    total_row = await cursor.fetchone()
    total = total_row['count'] if total_row else 0

    # 计算偏移量
    offset = (page - 1) * page_size

    # 构建排序
    order_clause = f"{sort} {order.upper()}"

    # 获取文件列表
    now = datetime.datetime.now()
    list_query = f"""
        SELECT id, filename, file_hash, local_path, oss_path, expire_at, created_at
        FROM files
        WHERE {where_clause}
        ORDER BY {order_clause}
        LIMIT ? OFFSET ?
    """
    cursor = await conn.execute(list_query, params + [page_size, offset])
    rows = await cursor.fetchall()
    await conn.close()

    # 构建结果
    items = []
    for row in rows:
        # 获取文件大小
        file_size = 0
        local_path = Path(Config.UPLOAD_DIR) / row['local_path']
        if local_path.exists():
            file_size = local_path.stat().st_size

        # 判断是否过期 (SQLite 返回的是字符串，需要转换为 datetime)
        is_expired = False
        if row['expire_at']:
            expire_at = datetime.datetime.fromisoformat(row['expire_at']) if isinstance(row['expire_at'], str) else row['expire_at']
            is_expired = expire_at < now

        items.append({
            "id": row['id'],
            "filename": row['filename'],
            "file_hash": row['file_hash'],
            "local_path": row['local_path'],
            "oss_path": row['oss_path'],
            # SQLite 已返回 ISO 格式字符串，无需调用 isoformat()
            "expire_at": row['expire_at'],
            "created_at": row['created_at'],
            "file_size": file_size,
            "is_expired": is_expired
        })

    total_pages = (total + page_size - 1) // page_size

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


async def get_file_detail(file_id: str) -> dict | None:
    """
    📄 获取文件详情

    Args:
        file_id: 文件 ID

    Returns:
        dict | None: 文件详情，不存在时返回 None
    """
    conn = await get_db_connection()
    cursor = await conn.execute(
        "SELECT * FROM files WHERE id = ?",
        (file_id,)
    )
    row = await cursor.fetchone()
    await conn.close()

    if not row:
        return None

    # 获取文件大小
    file_size = 0
    local_path = Path(Config.UPLOAD_DIR) / row['local_path']
    if local_path.exists():
        file_size = local_path.stat().st_size

    # 获取文件内容
    content = None
    content_bytes, filename = await retrieve_file_content(file_id)
    if content_bytes:
        try:
            content = content_bytes.decode('utf-8')
        except:
            content = None

    return {
        "id": row['id'],
        "filename": row['filename'],
        "file_hash": row['file_hash'],
        "hash_algorithm": row['hash_algorithm'],
        "local_path": row['local_path'],
        "oss_path": row['oss_path'],
        # SQLite 已返回 ISO 格式字符串，无需调用 isoformat()
        "expire_at": row['expire_at'],
        "created_at": row['created_at'],
        "file_size": file_size,
        "content": content
    }


async def delete_file(file_id: str) -> bool:
    """
    🗑️ 删除文件

    Args:
        file_id: 文件 ID

    Returns:
        bool: 是否删除成功
    """
    conn = await get_db_connection()

    # 获取文件信息
    cursor = await conn.execute("SELECT local_path, oss_path FROM files WHERE id = ?", (file_id,))
    row = await cursor.fetchone()

    if not row:
        await conn.close()
        return False

    # 删除本地文件
    local_path = Path(Config.UPLOAD_DIR) / row['local_path']
    if local_path.exists():
        try:
            await asyncio.to_thread(local_path.unlink)
        except Exception as e:
            log.error(f"删除本地文件失败 {local_path}: {e}")

    # 删除 OSS 文件
    if row['oss_path'] and Config.ENABLE_OSS:
        from app.core.oss_client import OSSClient
        try:
            await OSSClient.delete(row['oss_path'])
        except Exception as e:
            log.error(f"删除 OSS 文件失败 {row['oss_path']}: {e}")

    # 删除数据库记录
    await conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
    await conn.commit()
    await conn.close()

    # 清除缓存
    invalidate_file_cache(file_id)

    return True


async def batch_delete_files(file_ids: list[str]) -> dict:
    """
    🗑️ 批量删除文件

    Args:
        file_ids: 文件 ID 列表

    Returns:
        dict: 包含成功和失败数量的字典
    """
    success_count = 0
    failed_count = 0

    for file_id in file_ids:
        result = await delete_file(file_id)
        if result:
            success_count += 1
        else:
            failed_count += 1

    return {
        "success": success_count,
        "failed": failed_count
    }


async def get_storage_stats() -> dict:
    """
    📊 获取存储统计

    Returns:
        dict: 存储统计数据
    """
    conn = await get_db_connection()

    # 总文件数和大小
    cursor = await conn.execute("SELECT COUNT(*) as count FROM files")
    total_row = await cursor.fetchone()
    total_files = total_row['count'] if total_row else 0

    # 计算总存储大小
    total_size = 0
    by_type = {}
    by_expiry = {"permanent": 0, "1d": 0, "7d": 0, "1m": 0}
    expired_count = 0

    cursor = await conn.execute("SELECT local_path, filename, expire_at FROM files")
    rows = await cursor.fetchall()

    now = datetime.datetime.now()
    upload_dir = Path(Config.UPLOAD_DIR)

    for row in rows:
        # 获取文件大小
        local_path = upload_dir / row['local_path']
        size = 0
        if local_path.exists():
            size = local_path.stat().st_size
        total_size += size

        # 按类型统计
        ext = Path(row['filename']).suffix.lower() or "无后缀"
        by_type[ext] = by_type.get(ext, 0) + 1

        # 按过期时间统计
        if row['expire_at'] is None:
            by_expiry["permanent"] += 1
        else:
            # 计算过期天数 (SQLite 返回字符串，需要转换为 datetime)
            expire_at = datetime.datetime.fromisoformat(row['expire_at']) if isinstance(row['expire_at'], str) else row['expire_at']
            delta = (expire_at - now).days
            if delta < 0:
                expired_count += 1
            elif delta <= 1:
                by_expiry["1d"] += 1
            elif delta <= 7:
                by_expiry["7d"] += 1
            else:
                by_expiry["1m"] += 1

    await conn.close()

    return {
        "total_files": total_files,
        "total_size": total_size,
        "by_type": by_type,
        "by_expiry": by_expiry,
        "expired_count": expired_count
    }


async def get_upload_trend(days: int = 30) -> dict:
    """
    📈 获取上传趋势

    Args:
        days: 统计天数

    Returns:
        dict: 包含 dates, counts, sizes 的字典
    """
    conn = await get_db_connection()

    # 计算日期范围
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=days)

    # 查询每天的文件数量
    cursor = await conn.execute("""
        SELECT
            DATE(created_at) as date,
            COUNT(*) as count
        FROM files
        WHERE created_at >= ?
        GROUP BY DATE(created_at)
        ORDER BY date
    """, (start_date,))

    rows = await cursor.fetchall()
    await conn.close()

    # 构建完整的日期序列
    dates = []
    counts = []
    sizes = []

    for i in range(days):
        date = start_date + datetime.timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        dates.append(date_str)

        # 查找该日期的计数 (SQLite 的 DATE() 函数返回字符串，无需格式化)
        count = 0
        for row in rows:
            row_date = row['date'] if row['date'] else ""
            if row_date == date_str:
                count = row['count']
                break
        counts.append(count)
        sizes.append(0)  # 暂不返回大小趋势

    return {
        "dates": dates,
        "counts": counts,
        "sizes": sizes
    }


async def get_expiring_files(days: int = 7) -> dict:
    """
    ⏰ 获取即将过期的文件

    Args:
        days: 天数范围

    Returns:
        dict: 包含即将过期文件信息的字典
    """
    conn = await get_db_connection()

    # 计算时间范围
    now = datetime.datetime.now()
    end_date = now + datetime.timedelta(days=days)

    # 查询即将过期的文件
    cursor = await conn.execute("""
        SELECT id, filename, expire_at
        FROM files
        WHERE expire_at IS NOT NULL
            AND expire_at > ?
            AND expire_at <= ?
        ORDER BY expire_at ASC
    """, (now, end_date))

    rows = await cursor.fetchall()
    await conn.close()

    files = []
    for row in rows:
        # SQLite 返回字符串，需要转换为 datetime
        expire_at = datetime.datetime.fromisoformat(row['expire_at']) if isinstance(row['expire_at'], str) else row['expire_at']
        delta = (expire_at - now).days
        files.append({
            "id": row['id'],
            "filename": row['filename'],
            "expire_at": row['expire_at'],  # 已是 ISO 格式字符串
            "days_until_expiry": max(0, delta)
        })

    return {
        "expiring_soon": len(files),
        "files": files
    }


async def manual_cleanup() -> dict:
    """
    🧹 手动触发清理过期文件

    Returns:
        dict: 清理结果
    """
    conn = await get_db_connection()
    now = datetime.datetime.now()

    # 查询过期文件
    cursor = await conn.execute("SELECT id, local_path, oss_path FROM files WHERE expire_at < ?")
    rows = await cursor.fetchall()

    if not rows:
        await conn.close()
        return {"cleaned": 0, "message": "没有过期文件需要清理"}

    cleaned = 0

    for row in rows:
        file_id = row['id']
        local_path = Path(Config.UPLOAD_DIR) / row['local_path']

        # 删除本地文件
        if local_path.exists():
            try:
                await asyncio.to_thread(local_path.unlink)
            except Exception as e:
                log.error(f"删除本地文件失败 {local_path}: {e}")

        # 删除 OSS 文件
        if row['oss_path'] and Config.ENABLE_OSS:
            from app.core.oss_client import OSSClient
            try:
                await OSSClient.delete(row['oss_path'])
            except Exception as e:
                log.error(f"删除 OSS 文件失败 {row['oss_path']}: {e}")

        # 删除数据库记录
        await conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
        invalidate_file_cache(file_id)
        cleaned += 1

    await conn.commit()
    await conn.close()

    return {"cleaned": cleaned, "message": f"已清理 {cleaned} 个过期文件"}


# ==========================================
# 👁️ 文件系统监控任务
# ==========================================

async def sync_missing_files_task():
    """
    👁️ 同步丢失文件任务

    功能:
        - 定期扫描数据库中的文件记录
        - 检查磁盘文件是否存在
        - 自动清理丢失文件的数据库记录

    运行周期:
        - 每 30 秒执行一次

    注意:
        - 处理磁盘文件被直接删除的情况
        - 保证数据库与磁盘状态一致
    """
    log.info("👁️ 文件同步任务已启动，每 30 秒执行一次")

    while True:
        try:
            conn = await get_db_connection()

            # 查询所有文件记录
            cursor = await conn.execute("SELECT id, local_path FROM files")
            rows = await cursor.fetchall()
            await conn.close()

            missing_count = 0
            for row in rows:
                file_id = row['id']
                local_path = Path(Config.UPLOAD_DIR) / row['local_path']

                # 检查文件是否存在
                if not local_path.exists():
                    missing_count += 1
                    log.info(f"🗑️ 发现丢失文件: {file_id}，清理数据库记录")
                    conn = await get_db_connection()
                    await conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
                    await conn.commit()
                    await conn.close()
                    invalidate_file_cache(file_id)

            if missing_count > 0:
                log.info(f"✅ 同步任务完成，清理 {missing_count} 个丢失文件记录")

        except Exception as e:
            log.error(f"🚨 文件同步任务错误: {e}")

        # 等待 30 秒后再次执行
        await asyncio.sleep(30)


# ==========================================
# 📊 Prometheus 指标解析
# ==========================================

# 缓存 Prometheus 指标结果（10秒过期）
_metrics_cache: TTLCache = TTLCache(maxsize=1, ttl=10)
_metrics_cache_time: float = 0
_startup_time: float = time.time()


def _parse_prometheus_labels(labels_str: str) -> dict:
    """
    解析 Prometheus 标签字串

    Args:
        labels_str: 标签字串，如 'method="GET",path="/api"'

    Returns:
        dict: 解析后的标签字典
    """
    labels = {}
    for match in re.finditer(r'(\w+)="([^"]*)"', labels_str):
        labels[match.group(1)] = match.group(2)
    return labels


async def get_prometheus_metrics() -> dict:
    """
    📊 获取 Prometheus 监控指标（JSON 格式）

    通过访问 /metrics 端点获取 Prometheus 格式数据，
    解析后返回前端可用的 JSON 结构。

    Returns:
        dict: 包含 requests, latency, errors, system 的指标字典

    指标说明:
        - requests: 请求统计（总数、QPS、按方法/路径分组）
        - latency: 延迟统计（p50/p90/p95/p99 平均）
        - errors: 错误统计（总数、错误率、按状态码分组）
        - system: 系统指标（运行时长、内存使用）
    """
    global _metrics_cache_time

    current_time = time.time()
    if current_time - _metrics_cache_time < 10 and _metrics_cache:
        return _metrics_cache

    import httpx

    result = {
        "requests": {
            "total": 0,
            "qps": 0,
            "by_method": {},
            "by_path": {}
        },
        "latency": {
            "p50": 0,
            "p90": 0,
            "p95": 0,
            "p99": 0,
            "avg": 0
        },
        "errors": {
            "total": 0,
            "rate": 0,
            "by_status": {}
        },
        "system": {
            "uptime": int(current_time - _startup_time),
            "memory_usage": 0,
            "total_memory": 0,
            "cpu_usage": 0
        }
    }

    try:
        # 访问本地 metrics 端点
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:8000/metrics")
            metrics_text = response.text
    except Exception as e:
        log.warning(f"📊 获取 Prometheus 指标失败: {e}")
        return result

    # ========== 解析 http_server_requests_count ==========
    total_requests = 0
    status_counts = {}

    for match in re.finditer(
        r'http_server_requests_count\{([^}]*)\} (\d+)',
        metrics_text
    ):
        labels_str = match.group(1)
        value = int(match.group(2))
        labels = _parse_prometheus_labels(labels_str)

        method = labels.get("method", "UNKNOWN")
        path = labels.get("path", "")
        status = labels.get("status_code", "")

        total_requests += value

        # 按方法分组
        if method:
            result["requests"]["by_method"][method] = \
                result["requests"]["by_method"].get(method, 0) + value

        # 按路径分组（只统计前 10 个）
        if path and len(result["requests"]["by_path"]) < 10:
            result["requests"]["by_path"][path] = \
                result["requests"]["by_path"].get(path, 0) + value

        # 按状态码分组
        if status:
            status_counts[status] = status_counts.get(status, 0) + value
            # 4xx 和 5xx 视为错误
            if status.startswith(("4", "5")):
                result["errors"]["total"] += value
                result["errors"]["by_status"][status] = \
                    result["errors"]["by_status"].get(status, 0) + value

    result["requests"]["total"] = total_requests

    # 计算 QPS（基于运行时长）
    uptime = current_time - _startup_time
    if uptime > 0:
        result["requests"]["qps"] = round(total_requests / uptime, 2)

    # 计算错误率
    if total_requests > 0:
        result["errors"]["rate"] = round(
            (result["errors"]["total"] / total_requests) * 100, 2
        )

    # ========== 解析 http_server_requests_duration_seconds_bucket ==========
    # 解析延迟直方图数据
    latency_buckets: dict[str, list[float]] = {}

    for match in re.finditer(
        r'http_server_requests_duration_seconds_bucket\{([^}]*)\} (\d+)',
        metrics_text
    ):
        labels_str = match.group(1)
        value = int(match.group(2))
        labels = _parse_prometheus_labels(labels_str)

        le = labels.get("le", "")
        if le == "+Inf":
            continue

        if le not in latency_buckets:
            latency_buckets[le] = []
        latency_buckets[le].append(value)

    # 计算分位数（基于所有路径的数据）
    if latency_buckets:
        # 获取所有桶中的最大值（总量）
        bucket_values = []
        for le in sorted(latency_buckets.keys(), key=float):
            if latency_buckets[le]:
                bucket_values.append(max(latency_buckets[le]))

        if bucket_values:
            total_samples = max(bucket_values) if bucket_values else 1

            # 估算分位数（基于 Prometheus 的桶分布）
            # p50: 0.1s, p90: 0.5s, p95: 0.75s, p99: 1s
            percentile_map = {"0.1": "p50", "0.5": "p90", "0.75": "p95", "1": "p99"}
            for le_str, key in percentile_map.items():
                # 找到对应的桶
                for le in latency_buckets:
                    if float(le) <= float(le_str) and latency_buckets[le]:
                        ratio = max(latency_buckets[le]) / total_samples if total_samples > 0 else 0
                        if ratio >= 0.5:
                            result["latency"][key] = int(float(le) * 1000)
                            break

            # 计算平均延迟（从 _sum 和 _count 指标）
            sum_match = re.search(
                r'http_server_requests_duration_seconds_sum\{[^}]*\} ([\d.]+)',
                metrics_text
            )
            count_match = re.search(
                r'http_server_requests_duration_seconds_count\{[^}]*\} (\d+)',
                metrics_text
            )
            if sum_match and count_match:
                total_sum = float(sum_match.group(1))
                total_count = int(count_match.group(1))
                if total_count > 0:
                    result["latency"]["avg"] = int((total_sum / total_count) * 1000)

    # ========== 系统指标 ==========
    try:
        # 内存信息（系统级）
        mem = psutil.virtual_memory()
        # 已用内存（MB）
        result["system"]["memory_usage"] = round((mem.total - mem.available) / 1024 / 1024, 2)
        # 内存总量（MB）
        result["system"]["total_memory"] = round(mem.total / 1024 / 1024, 2)

        # CPU 使用率（系统级，百分比）
        result["system"]["cpu_usage"] = round(psutil.cpu_percent(interval=0.1), 2)
    except Exception as e:
        log.warning(f"获取系统指标失败: {e}")

    # 更新缓存
    _metrics_cache.clear()
    _metrics_cache.update(result)
    _metrics_cache_time = current_time

    return result
