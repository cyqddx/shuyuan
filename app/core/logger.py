"""
=============================================
📝 日志配置模块
=============================================
模块名称: logger.py
模块功能:
    - 基于 Loguru 的结构化日志配置
    - 控制台彩色输出
    - 文件自动轮转 (按天切割，保留 30 天)
日志风格:
    - 表情 + 中文
    - 分级输出 (DEBUG/INFO/WARNING/ERROR/CRITICAL)

"""

import sys
from loguru import logger

# ========== 内部模块导入 ==========
from app.core.config import LOG_DIR
import os


# ==========================================
# 🔧 日志配置
# ==========================================

# 移除 Loguru 默认的 handler
logger.remove()


# ==========================================
# 📺 控制台输出 (彩色日志)
# ==========================================

# 格式: 时间 | 级别 | 模块:函数:行号 | 消息
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
           "<level>{level: <8}</level> | "
           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
           "<level>{message}</level>",
    level="INFO",  # 控制台只显示 INFO 及以上级别
    colorize=True,  # 启用彩色输出
)


# ==========================================
# 📁 文件输出 (日志文件)
# ==========================================

# 日志文件路径: logs/server_YYYY-MM-DD.log
log_file_path = os.path.join(LOG_DIR, "server_{time:YYYY-MM-DD}.log")

logger.add(
    log_file_path,
    rotation="00:00",      # 每天午夜切割日志
    retention="30 days",   # 保留 30 天的日志
    level="INFO",          # 记录 INFO 及以上级别
    encoding="utf-8",      # UTF-8 编码 (支持中文)
    compression="gz",      # 压缩旧日志文件 (节省空间)
    backtrace=True,        # 显示完整的堆栈跟踪
    diagnose=True,         # 显示变量值
)


# ==========================================
# 📤 导出日志实例
# ==========================================

# 导出配置好的 logger 供其他模块使用
log = logger

__all__ = ["log"]
