"""
=============================================
🧪 pytest 配置和 fixtures
=============================================
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

import pytest

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_upload_dir():
    """临时上传目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_db_file():
    """临时数据库文件"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # 清理
    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass


@pytest.fixture
def mock_config(temp_upload_dir, temp_db_file, monkeypatch):
    """模拟配置"""
    monkeypatch.setenv("HOST_DOMAIN", "http://test.local:8000")
    monkeypatch.setenv("UPLOAD_DIR", temp_upload_dir)
    monkeypatch.setenv("DB_FILE", temp_db_file)
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("ENCRYPTION_ENABLED", "false")
    monkeypatch.setenv("COMPRESSION_ENABLED", "false")
    monkeypatch.setenv("ENABLE_OSS", "false")
    monkeypatch.setenv("REDIS_URL", "")

    # 重新导入 Config 以应用新的环境变量
    from app.core.config import Settings
    from app.core import config

    # 强制重新加载配置
    config.Config = Settings()

    return config.Config
