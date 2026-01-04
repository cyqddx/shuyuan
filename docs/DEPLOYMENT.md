# 部署指南

## 生产环境部署

### 1. 环境要求

- **Python**: 3.12+
- **操作系统**: Linux/Windows/macOS
- **内存**: 512MB RAM（推荐 1GB）
- **磁盘**: 至少 100MB 可用空间

### 2. 配置检查清单

在部署前，请确认以下配置项：

- [ ] `HOST_DOMAIN` - 服务对外域名/IP
- [ ] `API_KEY` - 修改为强密码（如启用鉴权）
- [ ] `ENCRYPTION_KEY` - 生成加密密钥（如启用加密）
- [ ] `MAX_FILE_SIZE` - 设置合适的文件大小限制
- [ ] `CORS_ORIGINS` - 配置允许的跨域来源（生产环境不要用 `*`）
- [ ] `OSS_ENDPOINT` / `OSS_BUCKET` / `OSS_AK` / `OSS_SK` - 配置 OSS（如使用）
- [ ] `REDIS_URL` - 配置 Redis（如使用分布式限流）

### 3. 生成加密密钥

如需启用文件加密，请先生成密钥：

```bash
# 使用 Python 生成 Fernet 密钥
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 或使用 uv 运行
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

将生成的密钥填入 `.env` 文件的 `ENCRYPTION_KEY` 配置项。

### 4. Docker 部署（推荐）

#### 4.1 准备配置文件

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置文件
vim .env
```

#### 4.2 构建并启动

```bash
# 构建并启动服务
docker-compose up -d --build

# 查看日志
docker-compose logs -f tuchuang

# 查看状态
docker-compose ps
```

#### 4.3 健康检查

```bash
# 检查服务状态
curl http://your-domain:8000/health

# 预期响应
{
  "status": "🟢 healthy",
  "version": "1.0.0",
  "components": {
    "database": "🟢 OK",
    "encryption": "🟢 Enabled" / "🔴 Disabled",
    "compression": "🟢 Enabled" / "🔴 Disabled",
    "oss": "🟢 Enabled" / "🔴 Disabled",
    "redis": "🟢 Connected" / "🔴 Disabled"
  }
}
```

#### 4.4 停止服务

```bash
# 停止服务
docker-compose down

# 停止并删除数据卷（谨慎操作）
docker-compose down -v
```

### 5. 本地部署（使用 uv）

#### 5.1 安装依赖

```bash
# 安装 uv 包管理器
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装依赖
uv sync
```

#### 5.2 配置环境

```bash
# 复制配置文件
cp .env.example .env

# 编辑配置
vim .env
```

#### 5.3 启动服务

```bash
# 开发模式（支持热重载）
uv run main.py

# 或使用 uvicorn
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

### 6. 监控和日志

#### 6.1 Prometheus 指标

访问 `/metrics` 端点获取监控指标：

```bash
curl http://your-domain:8000/metrics
```

可用指标：
- `http_server_requests_count` - 请求总数
- `http_server_requests_duration_seconds` - 请求延迟
- `http_server_requests_exceptions_total` - 异常总数

#### 6.2 日志

日志文件位置：`./logs/`

- `server_YYYY-MM-DD.log` - 应用日志
- 自动按天切割
- 保留 30 天

查看实时日志：

```bash
tail -f logs/server_$(date +%Y-%m-%d).log
```

### 7. 备份

#### 7.1 数据目录

需要备份的目录和文件：

- `./files.db` - 数据库文件
- `./uploads/` - 本地存储的文件
- `.env` - 配置文件（包含敏感信息）

#### 7.2 备份脚本示例

```bash
#!/bin/bash
BACKUP_DIR="/backup/tuchuang"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# 备份数据库
cp files.db $BACKUP_DIR/files_$DATE.db

# 备份上传文件
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz uploads/

# 保留最近 7 天的备份
find $BACKUP_DIR -name "*.db" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
```

### 8. 故障排查

#### 8.1 服务无法启动

```bash
# 检查配置文件语法
uv run python -c "from app.core.config import Config; print(Config)"

# 检查数据库
uv run python -c "import aiosqlite; import asyncio; asyncio.run(aiosqlite.connect('files.db'))"
```

#### 8.2 数据库锁定

SQLite 不支持多进程写入，确保只运行一个 worker：

```bash
# 错误示例
uvicorn main:app --workers 4  # ❌ 会锁死

# 正确示例
uvicorn main:app --workers 1  # ✅ 单 worker
```

#### 8.3 OSS 连接失败

- 检查网络连接：`ping oss-cn-hangzhou.aliyuncs.com`
- 验证凭证：确认 `OSS_AK` 和 `OSS_SK` 正确
- 检查 Bucket 确保存在且有权限

#### 8.4 限流不生效

- 确认 `REDIS_URL` 配置正确
- 测试 Redis 连接：`redis-cli -u REDIS_URL ping`

### 9. 安全建议

1. **HTTPS** - 生产环境务必使用 HTTPS
2. **API Key** - 使用强随机密钥，定期更换
3. **CORS** - 限制允许的来源，不要使用 `*`
4. **加密** - 敏感数据启用文件加密
5. **备份** - 定期备份数据库和文件
6. **日志** - 保护日志文件，避免泄露敏感信息
