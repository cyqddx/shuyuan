"""
=============================================
🧪 秒传 TTL 归属测试
=============================================
覆盖回归: 去重记录被秒传方共享, 新请求的有效期更长时必须延长记录,
且响应返回真实过期时间 (原先硬编码 "永久" 会撒谎)
"""

import datetime
import io

import pytest
from starlette.datastructures import UploadFile

import app.database as database
import app.services as services
from app.database import init_db, get_db_connection
from app.models import TimeLimit
from app.services import process_file_upload

CONTENT = b'{"bookSourceName":"ttl-test"}'


@pytest.fixture
def tmp_store(tmp_path, monkeypatch):
    """临时上传目录 + 临时数据库 (monkeypatch 模块常量)"""
    updir = tmp_path / "uploads"
    updir.mkdir()
    monkeypatch.setattr(services, "UPLOAD_DIR", str(updir))
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    return updir


def make_upload(name: str = "书源.json") -> UploadFile:
    return UploadFile(file=io.BytesIO(CONTENT), filename=name)


async def db_expire_at() -> datetime.datetime | None:
    conn = await get_db_connection()
    cursor = await conn.execute("SELECT expire_at FROM files LIMIT 1")
    row = await cursor.fetchone()
    await conn.close()
    if row["expire_at"] is None:
        return None
    if isinstance(row["expire_at"], str):
        return datetime.datetime.fromisoformat(row["expire_at"])
    return row["expire_at"]


@pytest.mark.asyncio
async def test_instant_upload_extends_ttl(tmp_store):
    """1天上传 → 永久秒传: 记录应延长为永久, 响应不再谎报"""
    await init_db()

    r1 = await process_file_upload(make_upload(), TimeLimit.ONE_DAY)
    assert r1["is_duplicate"] is False
    assert (await db_expire_at()) is not None

    r2 = await process_file_upload(make_upload(), TimeLimit.PERMANENT)
    assert r2["is_duplicate"] is True
    assert (await db_expire_at()) is None  # 已延长为永久
    assert r2["expiry"] == "永久"


@pytest.mark.asyncio
async def test_instant_upload_never_shortens(tmp_store):
    """永久上传 → 1天秒传: 记录不得被缩短"""
    await init_db()

    await process_file_upload(make_upload(), TimeLimit.PERMANENT)
    r2 = await process_file_upload(make_upload(), TimeLimit.ONE_DAY)

    assert (await db_expire_at()) is None
    assert r2["expiry"] == "永久"


@pytest.mark.asyncio
async def test_instant_upload_upgrade_partial(tmp_store):
    """1天上传 → 7天秒传: 过期时间升级到 7 天量级, 响应返回真实时间"""
    await init_db()

    await process_file_upload(make_upload(), TimeLimit.ONE_DAY)
    r2 = await process_file_upload(make_upload(), TimeLimit.SEVEN_DAYS)

    expire = await db_expire_at()
    assert expire is not None
    assert expire > datetime.datetime.now() + datetime.timedelta(days=6)
    assert r2["expiry"] != "永久"
    assert r2["expiry"] == str(expire)
