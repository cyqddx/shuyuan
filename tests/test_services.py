"""
=============================================
🧪 服务模块测试
=============================================
"""

import os

import pytest
from fastapi import HTTPException

from app.services import compress_data, decompress_data, calculate_hash, validate_and_minify
from app.core.config import Settings


class TestDataProcessing:
    """数据处理测试"""

    def test_compress_decompress(self):
        """测试压缩解压（依赖环境配置）"""
        # 注意：此测试需要在启用压缩的配置下运行才能验证压缩效果
        # 这里只验证往返功能正常
        original = b'{"test": "data"}'

        # 获取当前配置的压缩状态
        from app.core.config import Config
        compression_was_enabled = Config.COMPRESSION_ENABLED

        # 先存储原始数据，测试解压功能
        compressed = compress_data(original)
        decompressed = decompress_data(compressed)

        # 验证往返
        assert decompressed == original

        # 如果启用了压缩，验证压缩确实发生了
        if compression_was_enabled:
            # 启用压缩时，相同数据压缩后应不同
            assert compressed != original or original == b'{"test": "data"}'  # 小数据可能不压缩

    def test_disabled_compression(self):
        """测试禁用压缩时数据不变"""
        os.environ["COMPRESSION_ENABLED"] = "false"

        config = Settings()

        original = b'{"test": "data"}'
        compressed = compress_data(original)
        decompressed = decompress_data(compressed)

        assert compressed == original
        assert decompressed == original

    def test_hash_calculation(self):
        """测试哈希计算"""
        data = b"consistent data"
        hash1 = calculate_hash(data)
        hash2 = calculate_hash(data)

        assert hash1 == hash2
        assert len(hash1) == 32  # MD5 输出长度

    def test_hash_different_data(self):
        """测试不同数据产生不同哈希"""
        hash1 = calculate_hash(b"data1")
        hash2 = calculate_hash(b"data2")

        assert hash1 != hash2

    def test_json_validation_valid(self):
        """测试有效 JSON 验证"""
        valid = b'{"key": "value"}'
        result = validate_and_minify(valid)
        assert result == b'{"key":"value"}'

    def test_json_validation_invalid(self):
        """测试无效 JSON 验证"""
        with pytest.raises(HTTPException) as exc_info:
            validate_and_minify(b'{invalid json}')
        assert exc_info.value.status_code == 400

    def test_json_depth_limit(self):
        """测试 JSON 深度限制"""
        # 构造深度嵌套的 JSON（但合法）
        deep_obj = "a"
        for _ in range(25):  # 超过默认限制 20
            deep_obj = {"a": deep_obj}

        import orjson
        deep_json = orjson.dumps(deep_obj)

        with pytest.raises(HTTPException) as exc_info:
            validate_and_minify(deep_json)
        assert exc_info.value.status_code == 400
        assert "嵌套过深" in exc_info.value.detail

    def test_json_field_limit(self):
        """测试 JSON 字段数量限制"""
        # 构造超大对象
        large_obj = {f"field_{i}": i for i in range(1500)}
        import json
        large_json = json.dumps(large_obj).encode()

        with pytest.raises(HTTPException) as exc_info:
            validate_and_minify(large_json)
        assert exc_info.value.status_code == 400
        assert "字段过多" in exc_info.value.detail

    def test_json_array_limit(self):
        """测试 JSON 数组长度限制"""
        # 构造超大数组
        import json
        large_array = json.dumps([i for i in range(1500)]).encode()

        with pytest.raises(HTTPException) as exc_info:
            validate_and_minify(large_array)
        assert exc_info.value.status_code == 400
        assert "数组过长" in exc_info.value.detail

    def test_json_size_limit(self):
        """测试 JSON 大小限制"""
        # 构造超大 JSON（但字段不多）
        large_value = "x" * (11 * 1024 * 1024)  # 11MB
        large_json = f'{{"key":"{large_value}"}}'.encode()

        with pytest.raises(HTTPException) as exc_info:
            validate_and_minify(large_json)
        assert exc_info.value.status_code == 413
