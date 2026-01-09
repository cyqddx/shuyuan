"""
=============================================
👁️ 配置文件监听器模块
=============================================
模块名称: config_watcher.py
模块功能:
    - 使用 watchdog 监听 .env 文件变化
    - 防抖处理（避免频繁触发）
    - 线程安全的回调机制

依赖:
    - watchdog: 文件系统事件监听

使用场景:
    - 配置热重载
    - .env 文件修改监听

"""

import threading
import time
from pathlib import Path
from typing import Callable, Optional

# watchdog 文件系统监听
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

# 日志模块
from app.core.logger import log


class EnvFileHandler(FileSystemEventHandler):
    """
    📄 .env 文件变化处理器

    功能:
        - 监听 .env 文件的修改事件
        - 防抖处理（避免短时间内多次触发）
        - 触发配置重载回调

    属性:
        callback: 文件修改后的回调函数
        debounce_seconds: 防抖延迟（秒）
    """

    def __init__(self, callback: Callable[[], None], debounce_seconds: float = 1.0):
        """
        初始化文件处理器

        Args:
            callback: 文件修改后的回调函数
            debounce_seconds: 防抖延迟时间（秒），默认 1 秒
        """
        super().__init__()
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self._last_trigger: float = 0
        self._timer: Optional[threading.Timer] = None
        self._env_name = ".env"

    def on_modified(self, event):
        """
        文件修改事件处理

        Args:
            event: 文件系统事件
        """
        # 忽略目录事件
        if event.is_directory:
            return

        # 只处理 .env 文件
        if Path(event.src_path).name != self._env_name:
            return

        now = time.time()

        # 防抖：如果距离上次触发时间太短，则忽略
        if now - self._last_trigger < self.debounce_seconds:
            return

        self._last_trigger = now

        # 取消之前的定时器（如果存在）
        if self._timer:
            self._timer.cancel()

        # 延迟执行回调（确保文件写入完成）
        self._timer = threading.Timer(self.debounce_seconds, self._do_callback)
        self._timer.start()

    def _do_callback(self):
        """执行回调函数"""
        try:
            self.callback()
        except Exception as e:
            log.error(f"配置文件监听回调执行失败: {e}")


class ConfigWatcher:
    """
    👁️ 配置文件监听器

    功能:
        - 监听 .env 文件的变化
        - 文件修改后自动触发回调
        - 支持启动和停止监听

    使用示例:
        ```python
        def on_config_change():
            print("配置已修改，重新加载...")

        watcher = ConfigWatcher(Path(".env"), on_config_change)
        watcher.start()
        # ... 运行 ...
        watcher.stop()
        ```
    """

    def __init__(self, env_path: Path, callback: Callable[[], None]):
        """
        初始化配置监听器

        Args:
            env_path: .env 文件路径
            callback: 文件修改后的回调函数
        """
        self.env_path = env_path
        self.callback = callback
        self.observer: Optional[Observer] = None
        self._running = False

    def start(self):
        """启动文件监听"""
        if self._running:
            log.warning("配置文件监听已在运行中")
            return

        if not self.env_path.exists():
            log.warning(f"配置文件不存在: {self.env_path}")
            return

        try:
            # 创建观察者
            self.observer = Observer()

            # 创建事件处理器
            handler = EnvFileHandler(self.callback, debounce_seconds=1.0)

            # 监听 .env 文件所在的目录
            self.observer.schedule(
                handler,
                str(self.env_path.parent),
                recursive=False
            )

            # 启动观察者
            self.observer.start()
            self._running = True

            log.info(f"👁️ 配置文件监听已启动: {self.env_path}")

        except Exception as e:
            log.error(f"配置文件监听启动失败: {e}")
            self._running = False

    def stop(self):
        """停止文件监听"""
        if not self._running:
            return

        if self.observer:
            try:
                self.observer.stop()
                self.observer.join(timeout=5)
            except Exception as e:
                log.error(f"配置文件监听停止失败: {e}")
            finally:
                self.observer = None

        self._running = False
        log.info("🛑 配置文件监听已停止")

    @property
    def is_running(self) -> bool:
        """检查监听器是否正在运行"""
        return self._running

    def __repr__(self) -> str:
        return f"ConfigWatcher(path={self.env_path}, running={self._running})"


# ==========================================
# 📤 导出
# ==========================================

__all__ = [
    "ConfigWatcher",
    "EnvFileHandler",
]
