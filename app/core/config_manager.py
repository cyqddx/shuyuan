"""
=============================================
🔧 配置管理服务模块
=============================================
模块名称: config_manager.py
模块功能:
    - 读取和解析 .env 配置文件
    - 配置项验证和持久化
    - 触发服务重启
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from pydantic import BaseModel, Field, field_validator
from app.core.logger import log


# ==========================================
# 📋 配置项定义
# ==========================================

class ConfigItem(BaseModel):
    """单个配置项定义"""
    key: str = Field(..., description="配置键名")
    label: str = Field(..., description="显示名称")
    value: str = Field(..., description="当前值")
    type: str = Field(default="text", description="输入类型: text, number, boolean, select")
    category: str = Field(default="基础", description="配置分类")
    description: str = Field(default="", description="配置说明")
    options: Optional[list[str]] = Field(None, description="可选值列表")
    sensitive: bool = Field(default=False, description="是否敏感信息")
    placeholder: str = Field(default="", description="占位符")
    min_value: Optional[int] = Field(None, description="最小值（数字类型）")
    max_value: Optional[int] = Field(None, description="最大值（数字类型）")
    required: bool = Field(default=False, description="是否必填")
    pattern: Optional[str] = Field(None, description="正则验证模式")
    generate_command: Optional[str] = Field(None, description="生成命令（用于密钥等）")
    generate_type: Optional[str] = Field(None, description="生成类型：api_key, encryption_key")


class ConfigUpdateRequest(BaseModel):
    """配置更新请求"""
    updates: Dict[str, str] = Field(..., description="配置更新 {key: value}")


# ==========================================
# 📦 配置定义元数据
# ==========================================

CONFIG_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    # ==================== 基础配置 ====================
    "HOST_DOMAIN": {
        "label": "服务域名",
        "type": "text",
        "category": "基础",
        "description": "服务对外访问的域名或 IP 地址",
        "placeholder": "http://localhost:8000 或 https://yourdomain.com",
        "required": True,
    },

    # ==================== 鉴权配置 ====================
    "AUTH_ENABLED": {
        "label": "启用 API 鉴权",
        "type": "boolean",
        "category": "鉴权",
        "description": "开启后需要 API Key 才能访问",
    },
    "API_KEY": {
        "label": "API Key",
        "type": "text",
        "category": "鉴权",
        "description": "API 访问密钥",
        "sensitive": True,
        "placeholder": "请输入强密码或点击生成",
        "generate_type": "api_key",
    },

    # ==================== 加密配置 ====================
    "ENCRYPTION_ENABLED": {
        "label": "启用文件加密",
        "type": "boolean",
        "category": "加密",
        "description": "使用 AES-128 加密存储文件",
    },
    "ENCRYPTION_KEY": {
        "label": "加密密钥",
        "type": "text",
        "category": "加密",
        "description": "Fernet 加密密钥（32 字节 base64 编码）",
        "sensitive": True,
        "placeholder": "请输入密钥或点击生成",
        "generate_type": "encryption_key",
    },

    # ==================== 压缩配置 ====================
    "COMPRESSION_ENABLED": {
        "label": "启用文件压缩",
        "type": "boolean",
        "category": "压缩",
        "description": "使用 Gzip 压缩文件",
    },
    "COMPRESSION_LEVEL": {
        "label": "压缩等级",
        "type": "select",
        "category": "压缩",
        "description": "Gzip 压缩等级，越高压缩率越高但速度越慢",
        "options": ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
    },

    # ==================== OSS 配置 ====================
    "ENABLE_OSS": {
        "label": "启用 OSS 存储",
        "type": "boolean",
        "category": "OSS",
        "description": "启用阿里云 OSS 云存储",
    },
    "OSS_ENDPOINT": {
        "label": "OSS Endpoint",
        "type": "text",
        "category": "OSS",
        "description": "OSS 服务地址",
        "placeholder": "oss-cn-hangzhou.aliyuncs.com",
    },
    "OSS_BUCKET": {
        "label": "OSS Bucket",
        "type": "text",
        "category": "OSS",
        "description": "OSS 存储桶名称",
    },
    "OSS_AK": {
        "label": "OSS AccessKey ID",
        "type": "text",
        "category": "OSS",
        "description": "阿里云 AccessKey ID",
        "sensitive": True,
    },
    "OSS_SK": {
        "label": "OSS AccessKey Secret",
        "type": "text",
        "category": "OSS",
        "description": "阿里云 AccessKey Secret",
        "sensitive": True,
    },
    "OSS_DOMAIN": {
        "label": "OSS 访问域名",
        "type": "text",
        "category": "OSS",
        "description": "OSS 公网访问地址",
        "placeholder": "https://bucket.oss-cn-hangzhou.aliyuncs.com",
    },

    # ==================== 限流配置 ====================
    "RATE_LIMIT": {
        "label": "限流规则",
        "type": "select",
        "category": "限流",
        "description": "API 请求频率限制",
        "options": ["10/second", "30/second", "60/minute", "100/minute", "1000/hour"],
    },
    "REDIS_URL": {
        "label": "Redis 地址",
        "type": "text",
        "category": "限流",
        "description": "Redis 连接地址，留空使用内存限流",
        "placeholder": "redis://localhost:6379/0",
    },

    # ==================== 安全配置 ====================
    "MAX_FILE_SIZE": {
        "label": "最大文件大小（字节）",
        "type": "number",
        "category": "安全",
        "description": "上传文件大小限制",
        "min_value": 1024,
        "max_value": 104857600,  # 100MB
    },
    "CORS_ORIGINS": {
        "label": "CORS 允许来源",
        "type": "text",
        "category": "安全",
        "description": "允许跨域访问的来源，逗号分隔",
        "placeholder": "* 或 http://localhost:3000,https://yourdomain.com",
    },
}

# 配置分类顺序
CATEGORIES = [
    "基础",
    "鉴权",
    "加密",
    "压缩",
    "OSS",
    "限流",
    "安全",
]


# ==========================================
# 🛠️ 配置管理器
# ==========================================

class ConfigManager:
    """
    🔧 配置管理器

    负责:
        - 读取和解析 .env 文件
        - 配置项验证
        - 写入配置到 .env 文件
        - 触发服务重启
    """

    def __init__(self, env_path: Optional[Path] = None):
        """
        初始化配置管理器

        Args:
            env_path: .env 文件路径，默认为项目根目录下的 .env
        """
        if env_path is None:
            from app.core.config import PROJECT_ROOT
            env_path = PROJECT_ROOT / ".env"
        self.env_path = env_path
        self.backup_path = env_path.with_suffix(f".env.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}")

    def read_env_file(self) -> Dict[str, str]:
        """
        📖 读取 .env 文件

        Returns:
            dict: 配置键值对
        """
        config = {}
        if self.env_path.exists():
            with open(self.env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # 跳过空行和注释
                    if not line or line.startswith("#"):
                        continue
                    # 解析 KEY=VALUE
                    if "=" in line:
                        key, value = line.split("=", 1)
                        config[key.strip()] = value.strip()
        return config

    def write_env_file(self, config: Dict[str, str]) -> bool:
        """
        💾 写入 .env 文件

        Args:
            config: 配置键值对

        Returns:
            bool: 是否写入成功
        """
        try:
            # 备份原文件
            if self.env_path.exists():
                shutil.copy2(self.env_path, self.backup_path)
                log.info(f"📦 已备份原配置到: {self.backup_path.name}")

            # 写入新配置
            with open(self.env_path, "w", encoding="utf-8") as f:
                for key, value in config.items():
                    f.write(f"{key}={value}\n")

            log.info(f"✅ 配置已写入: {self.env_path}")
            return True
        except Exception as e:
            log.error(f"❌ 写入配置失败: {e}")
            return False

    def get_config_items(self) -> list[ConfigItem]:
        """
        📋 获取所有配置项

        Returns:
            list[ConfigItem]: 配置项列表（按分类排序）
        """
        current_config = self.read_env_file()
        items = []

        for key, definition in CONFIG_DEFINITIONS.items():
            value = current_config.get(key, "")
            # 敏感信息脱敏
            display_value = self._mask_sensitive(value, definition.get("sensitive", False))

            items.append(ConfigItem(
                key=key,
                label=definition["label"],
                value=display_value,
                type=definition.get("type", "text"),
                category=definition["category"],
                description=definition.get("description", ""),
                options=definition.get("options"),
                sensitive=definition.get("sensitive", False),
                placeholder=definition.get("placeholder", ""),
                min_value=definition.get("min_value"),
                max_value=definition.get("max_value"),
                required=definition.get("required", False),
                pattern=definition.get("pattern"),
                generate_command=definition.get("generate_command"),
                generate_type=definition.get("generate_type"),
            ))

        # 按分类排序
        category_order = {cat: i for i, cat in enumerate(CATEGORIES)}
        items.sort(key=lambda x: (category_order.get(x.category, 999), x.label))

        return items

    def update_config(self, updates: Dict[str, str]) -> tuple[bool, str]:
        """
        🔄 更新配置

        Args:
            updates: 配置更新 {key: value}

        Returns:
            tuple[bool, str]: (是否成功, 消息)
        """
        try:
            # 读取当前配置
            current_config = self.read_env_file()

            # 应用更新
            for key, value in updates.items():
                if key not in CONFIG_DEFINITIONS:
                    return False, f"❌ 未知的配置项: {key}"

                # 处理布尔值
                definition = CONFIG_DEFINITIONS[key]
                if definition.get("type") == "boolean":
                    current_config[key] = "true" if value.lower() in ("true", "1", "yes") else "false"
                else:
                    current_config[key] = value

            # 写入文件
            if self.write_env_file(current_config):
                changed = ", ".join(updates.keys())
                return True, f"✅ 配置已更新: {changed}"
            else:
                return False, "❌ 写入配置文件失败"

        except Exception as e:
            log.exception("更新配置异常")
            return False, f"❌ 更新配置失败: {str(e)}"

    def restart_service(self) -> tuple[bool, str]:
        """
        🔄 重启服务

        Returns:
            tuple[bool, str]: (是否成功, 消息)
        """
        try:
            # 检测运行环境
            if os.path.exists("/.dockerenv"):
                # Docker 环境：使用 supervisor 或直接退出让容器重启
                if os.path.exists("/usr/bin/supervisorctl"):
                    os.system("supervisorctl restart tuchuang")
                    return True, "✅ 服务重启命令已发送"
                else:
                    # 直接退出，让 Docker 容器管理器重启
                    return True, "✅ 配置已保存，服务将在几秒后自动重启"
            else:
                # 本地开发环境：尝试使用 supervisor
                result = os.system("supervisorctl restart tuchuang 2>/dev/null")
                if result == 0:
                    return True, "✅ 服务重启成功"
                else:
                    return True, "✅ 配置已保存，请手动重启服务"

        except Exception as e:
            log.exception("重启服务异常")
            return False, f"❌ 重启服务失败: {str(e)}"

    def _mask_sensitive(self, value: str, sensitive: bool) -> str:
        """
        🔒 脱敏敏感信息

        Args:
            value: 原始值
            sensitive: 是否敏感

        Returns:
            str: 脱敏后的值
        """
        if not sensitive:
            return value
        if not value or len(value) < 4:
            return "******"
        return value[:2] + "******" + value[-2:] if len(value) > 8 else "******"


# ==========================================
# 📤 导出
# ==========================================

__all__ = [
    "ConfigManager",
    "ConfigItem",
    "ConfigUpdateRequest",
    "CONFIG_DEFINITIONS",
    "CATEGORIES",
]
