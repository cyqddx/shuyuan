"""
=============================================
🗄️ 数据库模块
=============================================
模块名称: database.py
模块功能:
    - 异步 SQLite 数据库连接管理
    - 表结构初始化
    - 数据库连接池 (通过 aiosqlite)
    - 自动迁移: 兼容旧数据库，自动添加 hash_algorithm 字段
数据表:
    - files: 文件元数据表 (id, file_hash, hash_algorithm, filename, local_path, oss_path, expire_at, created_at)

使用的 Python 标准库模块:
    - contextlib.asynccontextmanager: 异步上下文管理器，用于连接池

"""

import aiosqlite

# ========== 内部模块导入 ==========
from app.core.config import DB_PATH
from app.core.logger import log


# ==========================================
# 🔗 数据库连接
# ==========================================

async def get_db_connection() -> aiosqlite.Connection:
    """
    🔗 获取异步数据库连接

    创建一个新的数据库连接，使用 Row 模式返回结果

    Returns:
        aiosqlite.Connection: SQLite 异步连接对象

    注意:
        - 每次调用创建新连接 (aiosqlite 内部有连接池)
        - 使用完毕后需要手动关闭连接
        - 建议使用 async with 语法自动管理
    """
    conn = await aiosqlite.connect(str(DB_PATH))
    # 设置 Row 工厂，可以通过列名访问
    conn.row_factory = aiosqlite.Row
    # WAL 模式允许读写并发，避免 "database is locked"
    await conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ==========================================
# 🏗️ 数据库初始化
# ==========================================

async def init_db():
    """
    🚀 初始化数据库表结构

    创建所有必要的表和索引:
        - files 表: 存储文件元数据
        - idx_hash / idx_hash_algorithm 索引: 加速哈希查重
        - idx_hash_unique 唯一索引: 防止并发重复插入
        - hash_algorithm 字段迁移（兼容旧数据库）

    注意:
        - 使用 IF NOT EXISTS 安全地创建表，幂等操作
    """
    log.info("🗄️ 正在初始化数据库...")

    conn = await get_db_connection()
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY,         -- 文件唯一 ID (16 位十六进制)
                file_hash TEXT,              -- 内容哈希 (用于去重)
                hash_algorithm TEXT DEFAULT 'md5',  -- 哈希算法 (blake2b 或 md5)
                filename TEXT,               -- 原始文件名
                local_path TEXT,             -- 本地存储路径
                oss_path TEXT,               -- OSS 访问 URL (可选)
                expire_at TIMESTAMP,         -- 过期时间 (NULL 表示永久)
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- 创建时间
            )
        """)

        # ========== 迁移：添加 hash_algorithm 字段（兼容旧数据库）==========
        cursor = await conn.execute("PRAGMA table_info(files)")
        columns = await cursor.fetchall()
        if "hash_algorithm" not in [col["name"] for col in columns]:
            log.info("🔄 正在迁移数据库：添加 hash_algorithm 字段...")
            await conn.execute("ALTER TABLE files ADD COLUMN hash_algorithm TEXT DEFAULT 'md5'")
            await conn.execute("UPDATE files SET hash_algorithm = 'md5' WHERE hash_algorithm IS NULL")
            log.info("✅ 数据库迁移完成")

        # ========== 索引 ==========
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_hash ON files (file_hash)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_hash_algorithm ON files (hash_algorithm)")
        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_hash_unique
            ON files (file_hash, hash_algorithm)
        """)

        await conn.commit()
    finally:
        await conn.close()

    log.info("✅ 数据库初始化完成")


# ==========================================
# 📤 导出函数
# ==========================================

__all__ = [
    "get_db_connection",  # 获取数据库连接
    "init_db",            # 初始化数据库
]
