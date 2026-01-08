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
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

# ========== 内部模块导入 ==========
from app.core.config import Config
from app.core.logger import log


# ==========================================
# 🏊 数据库连接池
# ==========================================

class DatabasePool:
    """
    🏊 简单的数据库连接池

    复用数据库连接，减少创建/销毁开销
    """

    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self.pool_size = pool_size
        self._connections: list[aiosqlite.Connection] = []
        self._initialized = False

    async def initialize(self):
        """初始化连接池"""
        if self._initialized:
            return

        for _ in range(self.pool_size):
            conn = await aiosqlite.connect(self.db_path)
            conn.row_factory = aiosqlite.Row
            self._connections.append(conn)

        self._initialized = True
        log.info(f"🗄️ 数据库连接池已初始化（大小: {self.pool_size}）")

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """
        获取连接（context manager）

        Yields:
            aiosqlite.Connection: 数据库连接
        """
        if not self._initialized:
            await self.initialize()

        conn = self._connections.pop()
        try:
            yield conn
        finally:
            self._connections.append(conn)

    async def close_all(self):
        """关闭所有连接"""
        for conn in self._connections:
            await conn.close()
        self._connections.clear()
        self._initialized = False
        log.info("🗄️ 数据库连接池已关闭")


# 全局连接池实例
_db_pool: DatabasePool | None = None


def get_db_pool() -> DatabasePool:
    """获取数据库连接池单例"""
    global _db_pool
    if _db_pool is None:
        _db_pool = DatabasePool(str(Config.DB_FILE), pool_size=5)
    return _db_pool


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
    conn = await aiosqlite.connect(Config.DB_FILE)
    # 设置 Row 工厂，可以通过列名访问
    conn.row_factory = aiosqlite.Row
    return conn


# ==========================================
# 🏗️ 数据库初始化
# ==========================================

async def init_db():
    """
    🚀 初始化数据库表结构

    创建所有必要的表和索引:
        - files 表: 存储文件元数据
        - idx_hash 索引: 加速哈希查重
        - idx_hash_unique 唯一索引: 防止并发重复插入

    注意:
        - 使用 IF NOT EXISTS 安全地创建表
        - 每次应用启动时调用，幂等操作
        - 初始化连接池
    """

    log.info("🗄️ 正在初始化数据库...")

    # 初始化连接池
    pool = get_db_pool()
    await pool.initialize()

    # 使用连接池获取连接
    async with pool.acquire() as conn:
        # ========== 创建文件表 ==========
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY,         -- 文件唯一 ID (8 位十六进制)
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
        # 检查字段是否已存在
        cursor = await conn.execute("PRAGMA table_info(files)")
        columns = await cursor.fetchall()
        column_names = [col["name"] for col in columns]

        if "hash_algorithm" not in column_names:
            log.info("🔄 正在迁移数据库：添加 hash_algorithm 字段...")
            await conn.execute("ALTER TABLE files ADD COLUMN hash_algorithm TEXT DEFAULT 'md5'")
            # 为现有记录设置默认值
            await conn.execute("UPDATE files SET hash_algorithm = 'md5' WHERE hash_algorithm IS NULL")
            log.info("✅ 数据库迁移完成")
        else:
            log.info("ℹ️ hash_algorithm 字段已存在，跳过迁移")

        # ========== 创建哈希索引 (加速去重查询) ==========
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_hash
            ON files (file_hash)
        """)

        # ========== 创建哈希算法索引 ==========
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_hash_algorithm
            ON files (hash_algorithm)
        """)

        # ========== 创建哈希唯一索引 (防止并发重复) ==========
        # 注意: SQLite 中 UNIQUE INDEX 会自动处理并发插入冲突
        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_hash_unique
            ON files (file_hash, hash_algorithm)
        """)

        # 提交更改
        await conn.commit()

    log.info("✅ 数据库初始化完成")


async def close_db():
    """
    🔒 关闭数据库连接池

    应用关闭时调用，确保所有连接正确关闭
    """
    global _db_pool
    if _db_pool:
        await _db_pool.close_all()
        _db_pool = None


# ==========================================
# 📤 导出函数
# ==========================================

__all__ = [
    "get_db_connection",  # 获取数据库连接
    "init_db",            # 初始化数据库
    "close_db",           # 关闭数据库连接池
    "get_db_pool",        # 获取连接池
]
