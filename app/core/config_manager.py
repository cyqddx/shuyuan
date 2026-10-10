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
from pathlib import Path
from typing import Dict, Any, Optional

from app.models import ConfigItem
from app.core.logger import log


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
    "API_KEYS": {
        "label": "多 API Key",
        "type": "text",
        "category": "鉴权",
        "description": "逗号分隔的多个 API Key（设置后优先于单个 API Key，泄露可单独移除）",
        "sensitive": True,
        "placeholder": "key-for-reader,key-for-script",
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
        💾 写入 .env 文件（直接修改对应字段，保留注释和其他内容）

        Args:
            config: 配置键值对

        Returns:
            bool: 是否写入成功
        """
        try:
            # 读取原文件内容
            if self.env_path.exists():
                with open(self.env_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            else:
                lines = []

            # 记录已处理的配置项
            processed_keys = set()

            # 遍历每一行，修改需要更新的配置
            new_lines = []
            for line in lines:
                stripped = line.strip()
                # 跳过注释和空行（直接保留）
                if not stripped or stripped.startswith("#"):
                    new_lines.append(line)
                    continue

                # 解析 KEY=VALUE
                if "=" in stripped:
                    key, _ = stripped.split("=", 1)
                    key = key.strip()
                    if key in config:
                        # 修改这一行
                        new_lines.append(f"{key}={config[key]}\n")
                        processed_keys.add(key)
                    else:
                        # 保留原行
                        new_lines.append(line)
                else:
                    # 保留原行
                    new_lines.append(line)

            # 添加新配置项（原文件中不存在的）
            for key, value in config.items():
                if key not in processed_keys:
                    new_lines.append(f"{key}={value}\n")

            # 写回文件
            with open(self.env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

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

        发送 SIGTERM 终止当前进程，由 systemd (Restart=always) 或
        Docker (restart: unless-stopped) 重新拉起，使新配置生效。
        """
        import signal
        os.kill(os.getpid(), signal.SIGTERM)
        return True, "✅ 配置已保存，服务正在重启"

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
    "CONFIG_DEFINITIONS",
    "CATEGORIES",
]
