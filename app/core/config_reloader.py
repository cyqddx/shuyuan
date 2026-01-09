"""
=============================================
🔄 配置重载协调器模块
=============================================
模块名称: config_reloader.py
模块功能:
    - 协调文件监听和配置重载
    - 配置变更日志记录
    - 线程安全的重载机制

使用场景:
    - 配置热重载
    - 自动响应 .env 文件变化

"""

from pathlib import Path
from typing import TYPE_CHECKING

# 类型注解
if TYPE_CHECKING:
    from app.core.config import Settings, ConfigProxy

# 日志模块
from app.core.logger import log


class ConfigReloader:
    """
    🔄 配置重载协调器

    功能:
        - 启动/停止 .env 文件监听
        - 文件变化时自动重新加载配置
        - 记录配置变更日志

    使用示例:
        ```python
        reloader = ConfigReloader()
        reloader.start_watching()
        # ... 运行 ...
        reloader.stop_watching()
        ```
    """

    def __init__(self, env_path: Path = None):
        """
        初始化配置重载器

        Args:
            env_path: .env 文件路径，默认使用项目根目录下的 .env
        """
        from app.core.config import PROJECT_ROOT

        if env_path is None:
            env_path = PROJECT_ROOT / ".env"

        self.env_path = env_path
        self._watcher = None

    def _on_file_changed(self):
        """
        📁 文件变化回调

        当 .env 文件被修改时，此函数会被调用。
        """
        log.info("🔄 检测到 .env 文件变化，开始重新加载配置...")
        self.reload()

    def reload(self) -> bool:
        """
        🔄 执行配置重载

        创建新的配置实例并替换当前配置。

        Returns:
            bool: 重载成功返回 True，失败返回 False
        """
        from app.core.config import Config, Settings

        try:
            # 创建新的配置实例（会重新读取 .env）
            new_settings = Settings()

            # 收集变更的配置项（用于日志）
            old_values = {}
            new_values = {}
            for key in new_settings.model_fields:
                old_val = getattr(Config._settings, key, None)
                new_val = getattr(new_settings, key, None)
                if old_val != new_val:
                    old_values[key] = old_val
                    new_values[key] = new_val

            # 执行重载
            success = Config.reload(new_settings)

            if success:
                log.info("✅ 配置热重载成功")
                log.info(f"   版本: {Config.version}")

                # 输出变更的配置项
                if old_values:
                    changes = []
                    for key in old_values:
                        old_v = old_values[key]
                        new_v = new_values[key]
                        # 敏感信息脱敏
                        if "key" in key.lower() or "secret" in key.lower() or "token" in key.lower():
                            old_v = "***" if old_v else None
                            new_v = "***" if new_v else None
                        changes.append(f"{key}: {old_v} → {new_v}")
                    log.info(f"   变更项: {', '.join(changes)}")
                else:
                    log.info("   无配置变更")

            else:
                log.error("❌ 配置热重载失败，请检查 .env 文件")

            return success

        except Exception as e:
            log.exception(f"💥 配置重载异常: {e}")
            return False

    def start_watching(self):
        """启动配置文件监听"""
        if self._watcher is None:
            from app.core.config_watcher import ConfigWatcher

            self._watcher = ConfigWatcher(self.env_path, self._on_file_changed)

        self._watcher.start()

    def stop_watching(self):
        """停止配置文件监听"""
        if self._watcher:
            self._watcher.stop()

    @property
    def is_running(self) -> bool:
        """检查监听器是否正在运行"""
        return self._watcher.is_running if self._watcher else False

    def __repr__(self) -> str:
        return f"ConfigReloader(path={self.env_path}, running={self.is_running})"


# ==========================================
# 📤 导出
# ==========================================

__all__ = [
    "ConfigReloader",
]
