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
        log.warning(f"🔍 文件已丢失: {local_path}")
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
