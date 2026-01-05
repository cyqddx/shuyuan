"""
=============================================
🚀 图床服务 - 应用入口模块
=============================================
模块名称: main.py
模块功能:
    - FastAPI 应用初始化与配置
    - 应用生命周期管理 (启动/关闭)
    - 中间件挂载 (CORS、限流、监控)
    - 路由注册

"""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

# FastAPI 核心组件
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 限流异常处理
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# 统一异常处理
from app.core.error_handler import (
    global_exception_handler,
    validation_exception_handler,
    http_exception_handler,
)
from fastapi.exceptions import RequestValidationError

# Prometheus 监控
from prometheus_fastapi_instrumentator import Instrumentator

# 路径处理
from pathlib import Path

# ========== 内部模块导入 ==========
# 应用配置 - 从 .env 读取所有配置
from app.core.config import Config, PROJECT_ROOT
# 日志模块 - 表情+中文风格日志
from app.core.logger import log
# 安全模块 - 限流器
from app.core.security import limiter
# HTTP 客户端 - 复用 TCP 连接
from app.core.http_client import http_client
# 加密引擎 - Fernet AES-128 加密
from app.core.crypto import CryptoEngine
# OSS 客户端 - 阿里云对象存储
from app.core.oss_client import OSSClient
# 数据库初始化
from app.database import init_db, close_db
# 后台清理任务
from app.services import clean_expired_task
# API 路由
from app.api import router


# ==========================================
# 🪵 拦截 Uvicorn 日志
# ==========================================

class InterceptHandler(logging.Handler):
    """拦截标准库日志，转发到 loguru"""

    def emit(self, record):
        # 使用 loguru 记录
        from loguru import logger as loguru_logger

        # 获取对应的 loguru 日志级别
        try:
            level = loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 查找调用者
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        loguru_logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# 配置日志拦截
logging.root.handlers = [InterceptHandler()]
logging.root.setLevel(logging.INFO)

# 禁用 Uvicorn/FastAPI 的访问日志
for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"]:
    logging_logger = logging.getLogger(logger_name)
    logging_logger.handlers = [InterceptHandler()]
    logging_logger.propagate = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    🔄 应用生命周期管理器

    启动流程:
        1. 输出启动日志
        2. 初始化数据库
        3. 启动 HTTP 客户端
        4. 初始化加密引擎 (如启用)
        5. 初始化 OSS 客户端 (如启用)
        6. 启动后台清理任务

    关闭流程:
        1. 输出关闭日志
        2. 优雅停止后台任务
        3. 关闭 HTTP 客户端

    Args:
        app: FastAPI 应用实例

    Yields:
        None - 应用运行期间在此等待
    """

    # ========== 启动阶段 ==========

    # 输出启动日志
    log.info("🚀 正在启动图床服务...")

    # 输出当前配置状态 (仅显示开关状态，不泄露敏感信息)
    log.info(
        f"⚙️ 配置状态: "
        f"鉴权={'🔴启用' if Config.AUTH_ENABLED else '⚪关闭'} | "
        f"加密={'🔴启用' if Config.ENCRYPTION_ENABLED else '⚪关闭'} | "
        f"压缩={'🔴启用' if Config.COMPRESSION_ENABLED else '⚪关闭'} | "
        f"OSS={'🔴启用' if Config.ENABLE_OSS else '⚪关闭'} | "
        f"Redis={'🔴启用' if bool(Config.REDIS_URL) else '⚪关闭'}"
    )

    # 初始化数据库 (创建表结构)
    log.info("🗄️ 正在初始化数据库...")
    await init_db()

    # 启动全局 HTTP 客户端 (复用 TCP 连接)
    log.info("🌐 正在启动 HTTP 客户端...")
    http_client.start()

    # 初始化加密引擎 (如果启用加密)
    # ⚠️ 如果加密开启但密钥错误/缺失，服务必须停止，防止明文数据泄露
    try:
        CryptoEngine.init_engine()
    except Exception as e:
        # 加密初始化失败是致命错误，必须停止服务
        log.critical(f"💥 加密引擎初始化失败，服务停止: {e}")
        raise

    # 初始化 OSS 客户端 (如果启用 OSS)
    OSSClient.init()

    # 启动后台清理任务 (每小时清理一次过期文件)
    log.info("🧹 正在启动后台清理任务...")
    task = asyncio.create_task(clean_expired_task())

    log.info("✅ 图床服务启动完成！")

    # ========== 运行阶段 ==========
    # 应用在此处运行，处理请求
    yield

    # ========== 关闭阶段 ==========

    log.info("🛑 正在关闭图床服务...")

    # 关闭数据库连接池
    await close_db()
    log.info("🗄️ 数据库连接池已关闭")

    # 优雅关闭后台任务 (等待最多 5 秒)
    try:
        await asyncio.wait_for(task, timeout=5)
        log.info("✅ 后台清理任务已正常停止")
    except asyncio.TimeoutError:
        # 超时则强制取消
        log.warning("⏰ 后台任务关闭超时，强制取消")
        task.cancel()
    except asyncio.CancelledError:
        log.info("✅ 后台清理任务已取消")

    # 关闭 HTTP 客户端
    await http_client.stop()
    log.info("🌐 HTTP 客户端已关闭")

    log.info("👋 图床服务已完全关闭")


# ==========================================
# 🏗️ FastAPI 应用实例化
# ==========================================

app = FastAPI(
    title="Tuchuang File Server",  # API 文档标题
    description="企业级文件直链托管服务",  # API 文档描述
    version="1.0.0",  # 版本号
    lifespan=lifespan,  # 生命周期管理器
    docs_url="/docs",  # Swagger UI 地址
    redoc_url="/redoc",  # ReDoc 地址
)


# ==========================================
# 📊 Prometheus 监控挂载
# ==========================================

# 暴露 /metrics 端点，供 Prometheus 抓取监控数据
# 包含: 请求数、延迟分布、错误率等指标
Instrumentator().instrument(app).expose(app)


# ==========================================
# 🌐 CORS 中间件配置
# ==========================================

# 跨域资源共享配置 - 控制哪些域名可以访问 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,  # 允许的来源 (从 .env 读取)
    allow_credentials=True,  # 允许携带凭证 (Cookie)
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
)


# ==========================================
# 🚦 限流异常处理挂载
# ==========================================

# 将限流器注册到应用状态
app.state.limiter = limiter

# 注册限流异常处理器 (超出限流时返回 429 错误)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ==========================================
# ⚠️ 统一异常处理挂载
# ==========================================

# 注册全局异常处理器 (未捕获的异常)
app.add_exception_handler(Exception, global_exception_handler)

# 注册参数校验异常处理器
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# 注册 HTTP 异常处理器 (统一格式)
app.add_exception_handler(HTTPException, http_exception_handler)


# ==========================================
# 📁 静态文件挂载
# ==========================================

# 挂载静态文件目录 (用于 favicon.ico 等静态资源)
static_dir = PROJECT_ROOT / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    log.info(f"📁 静态文件目录已挂载: {static_dir}")


# ==========================================
# 🎨 Favicon 路由 (根路径)
# ==========================================

# 浏览器默认从根路径请求 favicon.ico，这里重定向到静态文件
favicon_path = static_dir / "favicon.ico"
if favicon_path.exists():
    from fastapi import Response
    import aiofiles

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        """🎨 返回 favicon 图标"""
        async with aiofiles.open(favicon_path, "rb") as f:
            content = await f.read()
        return Response(content=content, media_type="image/x-icon")


# ==========================================
# 🛣️ API 路由挂载
# ==========================================

# 挂载所有 API 路由 (上传、下载、管理、健康检查等)
app.include_router(router)


# ==========================================
# 🏃 直接运行入口 (开发模式)
# ==========================================

if __name__ == "__main__":
    import uvicorn

    # 启动开发服务器 (支持热重载)
    uvicorn.run(
        "main:app",  # 应用模块路径
        host="0.0.0.0",  # 监听所有网络接口
        port=8000,  # 端口号
        reload=True,  # 开启热重载 (代码变更自动重启)
        access_log=False,  # 禁用访问日志 (使用 loguru 统一记录)
    )
