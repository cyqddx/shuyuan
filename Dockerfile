# ==========================================
# 🐳 图床服务 Docker 镜像
# ==========================================
# 基础镜像: Python 3.12 Slim
# 包含组件: FastAPI + aiosqlite + uvicorn
# ==========================================

FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装 uv 包管理器 (比 pip 快 10-100 倍)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 复制依赖配置文件
COPY pyproject.toml uv.lock ./

# 使用 uv 安装依赖到系统目录 (Docker 中不需要 venv)
# --system: 安装到系统 Python
# --no-cache: 不缓存下载的包，减小镜像体积
RUN uv pip install --system --no-cache -r pyproject.toml

# 复制应用源码
COPY app/ ./app/
COPY main.py ./
COPY static/ ./static/

# 创建必要的目录和空数据库文件
# 数据目录用于命名卷挂载，避免文件/目录类型冲突
RUN mkdir -p uploads logs data && \
    touch data/files.db && \
    chmod 666 data/files.db uploads logs

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# 启动命令
# --host 0.0.0.0: 监听所有网络接口
# --port 8000: 端口号
# --workers 1: 单进程 (SQLite 不支持多进程写入)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
