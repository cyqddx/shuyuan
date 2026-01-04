"""
=============================================
⚙️ 核心业务逻辑模块
=============================================
模块名称: services.py
模块功能:
    - 文件上传处理: 校验 -> 查重 -> 压缩 -> 加密 -> 存储
    - 文件读取处理: 读取 -> 解密 -> 解压 -> 返回
    - 后台清理任务: 定期清理过期文件
数据处理流程:
    写入: 接收文件 -> JSON 校验 -> 去重检查 -> 压缩 -> 加密 -> 存储
    读取: 读取文件 -> 解密 -> 解压 -> 返回 JSON

"""

# ========== 标准库导入 ==========
import os  # 路径操作
import uuid  # 唯一 ID 生成
import hashlib  # 哈希计算
import gzip  # Gzip 压缩
import datetime  # 时间处理
import asyncio  # 异步任务

# ========== 第三方库导入 ==========
import anyio  # 异步文件操作
import orjson  # 高性能 JSON 处理
from fastapi import UploadFile, HTTPException

# ========== 内部模块导入 ==========
from app.core.config import Config
from app.database import get_db_connection
from app.models import TimeLimit
from app.core.logger import log
from app.core.http_client import http_client
from app.core.crypto import CryptoEngine


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


def calculate_hash(content: bytes) -> str:
    """
    🔐 计算数据哈希

    使用 MD5 算法计算内容的哈希值，用于文件去重

    Args:
        content: 待计算的字节数据

    Returns:
        str: 32 位十六进制 MD5 哈希值

    注意:
        - MD5 虽然不安全用于密码，但用于文件去重足够
        - 相同内容必然产生相同哈希，实现"秒传"功能
    """
    return hashlib.md5(content).hexdigest()


def validate_and_minify(content: bytes) -> bytes:
    """
    ✅ 校验并压缩 JSON

    使用 orjson 校验 JSON 格式，并去除多余空格

    Args:
        content: 待校验的 JSON 字节数据

    Returns:
        bytes: 压缩后的 JSON 字节数据 (无空格、无换行)

    Raises:
        HTTPException: JSON 格式无效时抛出 400 错误

    注意:
        - orjson 比 stdlib json 快 5-10 倍
        - 强制校验确保存储的都是合法 JSON
    """
    try:
        # 解析 JSON (同时校验格式)
        obj = orjson.loads(content)
        # 序列化回 JSON (去除空格和换行)
        return orjson.dumps(obj)
    except orjson.JSONDecodeError:
        # JSON 格式无效
        raise HTTPException(status_code=400, detail="📄 JSON 格式无效，请检查文件内容")


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
    ext = os.path.splitext(file.filename)[1].lower()
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
    file_hash = calculate_hash(minified_content)

    conn = await get_db_connection()
    # 查询是否存在相同哈希的文件
    cursor = await conn.execute("SELECT id, oss_path FROM files WHERE file_hash = ?", (file_hash,))
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
    # 生成唯一的文件 ID (8 位十六进制)
    file_id = uuid.uuid4().hex[:8]

    # 确定存储文件名
    # 加密/压缩模式下使用 .bin 后缀，避免误导
    if Config.ENCRYPTION_ENABLED or Config.COMPRESSION_ENABLED:
        save_filename = f"{file_id}.bin"
    else:
        save_filename = f"{file_id}{ext}"

    # 6.1 本地存储
    local_path = os.path.join(Config.UPLOAD_DIR, save_filename)
    async with await anyio.open_file(local_path, 'wb') as f:
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
            INSERT INTO files (id, file_hash, filename, local_path, oss_path, expire_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (file_id, file_hash, file.filename, save_filename, oss_url, expire_at))
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
    conn = await get_db_connection()
    cursor = await conn.execute("SELECT local_path, filename FROM files WHERE id = ?", (file_id,))
    row = await cursor.fetchone()
    await conn.close()

    if not row:
        # 文件不存在
        log.warning(f"🔍 文件不存在: {file_id}")
        return None, None

    local_path = os.path.join(Config.UPLOAD_DIR, row['local_path'])
    original_name = row['filename']

    # ========== 2. 检查文件是否存在 ==========
    if not os.path.exists(local_path):
        log.warning(f"🔍 文件已丢失: {local_path}")
        return None, None

    # ========== 3. 读取文件内容 ==========
    try:
        async with await anyio.open_file(local_path, 'rb') as f:
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
    🧹 后台清理过期文件任务

    功能:
        - 定期扫描数据库中的过期文件
        - 删除本地文件
        - 删除 OSS 文件 (如果启用)
        - 删除数据库记录

    运行周期:
        - 每小时执行一次 (3600 秒)

    注意:
        - 这是一个无限循环的任务，在应用启动时创建
        - 异常会被捕获并记录，不会中断任务循环
    """

    log.info("🧹 后台清理任务已启动，每小时执行一次")

    while True:
        try:
            # ========== 1. 查询过期文件 ==========
            conn = await get_db_connection()
            now = datetime.datetime.now()

            # 查询所有过期文件
            cursor = await conn.execute("SELECT id, local_path, oss_path FROM files WHERE expire_at < ?", (now,))
            rows = await cursor.fetchall()

            if rows:
                log.info(f"🧹 发现 {len(rows)} 个过期文件需要清理")

            # ========== 2. 逐个处理过期文件 ==========
            for row in rows:
                fid = row['id']
                l_path = row['local_path']
                o_path = row['oss_path']

                # 2.1 删除本地文件
                full_path = os.path.join(Config.UPLOAD_DIR, l_path)
                if os.path.exists(full_path):
                    try:
                        os.remove(full_path)
                        log.info(f"🗑️ 清理任务: 已删除本地文件 {l_path}")
                    except OSError as e:
                        log.error(f"⚠️ 清理任务: 删除本地文件失败 {l_path}: {e}")

                # 2.2 删除 OSS 文件 (如果有)
                if o_path and Config.ENABLE_OSS:
                    try:
                        from app.core.oss_client import OSSClient
                        await OSSClient.delete(o_path)
                        log.info(f"☁️ 清理任务: 已删除 OSS 文件 {o_path}")
                    except Exception as e:
                        log.error(f"⚠️ 清理任务: 删除 OSS 文件失败 {o_path}: {e}")

                # 2.3 删除数据库记录
                await conn.execute("DELETE FROM files WHERE id = ?", (fid,))

            # ========== 3. 提交事务 ==========
            if rows:
                await conn.commit()
                log.info(f"✅ 清理任务完成，共清理 {len(rows)} 个文件")

            await conn.close()

        except Exception as e:
            # 捕获所有异常，防止任务循环中断
            log.error(f"🚨 清理任务严重错误: {e}")

        # ========== 4. 等待下次执行 ==========
        # 每小时执行一次 (3600 秒)
        await asyncio.sleep(3600)
