# 🚀 部署指南

本文档详细介绍图床服务的生产环境部署流程。

---

## 1. 环境要求

- **Python**: 3.12+
- **Node.js**: 18+ (仅管理后台需要)
- **操作系统**: Linux/Windows/macOS
- **内存**: 512MB RAM（推荐 1GB）
- **磁盘**: 至少 100MB 可用空间

---

## 2. 配置检查清单

在部署前，请确认以下配置项：

- [ ] `HOST_DOMAIN` - 服务对外域名/IP
- [ ] `API_KEY` - 修改为强密码（如启用鉴权）
- [ ] `ENCRYPTION_KEY` - 生成加密密钥（如启用加密）
- [ ] `MAX_FILE_SIZE` - 设置合适的文件大小限制
- [ ] `CORS_ORIGINS` - 配置允许的跨域来源（生产环境不要用 `*`）
- [ ] `OSS_ENDPOINT` / `OSS_BUCKET` / `OSS_AK` / `OSS_SK` - 配置 OSS（如使用）
- [ ] `REDIS_URL` - 配置 Redis（如使用分布式限流）

---

## 3. 生成加密密钥

如需启用文件加密，请先生成密钥：

```bash
# 使用 Python 生成 Fernet 密钥
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 或使用 uv 运行
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

将生成的密钥填入 `.env` 文件的 `ENCRYPTION_KEY` 配置项。

---

## 4. Docker 部署 (推荐)

### 4.1 准备配置文件

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置文件
vim .env
```

### 4.2 启动方式

#### 完整部署（前后端）

```bash
# 构建并启动服务
docker-compose up -d --build
```

访问地址：
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs
- 前端管理: http://localhost:3000

#### 仅启动后端

```bash
docker compose up -d --build tuchuang
```

### 4.3 常用命令

| 命令 | 说明 |
|------|------|
| `docker-compose up -d --build` | 构建并启动所有服务 |
| `docker compose up -d --build tuchuang` | 仅启动后端 |
| `docker-compose down` | 停止并删除所有服务 |
| `docker-compose logs -f` | 查看所有服务日志 |
| `docker-compose logs -f tuchuang` | 查看后端服务日志 |
| `docker-compose logs -f admin` | 查看前端服务日志 |
| `docker-compose restart` | 重启所有服务 |
| `docker-compose ps` | 查看服务状态 |

### 4.4 健康检查

```bash
# 检查服务状态
curl http://your-domain:8000/health
```

**预期响应：**
```json
{
  "status": "🟢 健康",
  "version": "1.0.0",
  "components": {
    "database": "🟢 正常",
    "encryption": "🟢 已启用" / "🔴 未启用",
    "compression": "🟢 已启用" / "🔴 未启用",
    "oss": "🟢 已启用" / "🔴 未启用",
    "redis": "🟢 已连接" / "🔴 未启用"
  }
}
```

### 4.5 停止服务

```bash
# 停止服务
docker-compose down

# 停止并删除数据卷（谨慎操作）
docker-compose down -v
```

---

## 5. 本地部署

### 5.1 后端部署

#### 安装依赖

```bash
# 安装 uv 包管理器
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装项目依赖
uv sync
```

#### 配置环境

```bash
# 复制配置文件
cp .env.example .env

# 编辑配置
vim .env
```

#### 启动服务

```bash
# 开发模式（支持热重载）
uv run main.py

# 或使用 uvicorn
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

### 5.2 前端部署

```bash
# 进入 admin 目录
cd admin

# 安装依赖
npm install

# 配置环境变量
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# 启动开发服务器
npm run dev

# 或构建生产版本
npm run build
npm start
```

---

## 6. 监控和日志

### 6.1 Prometheus 指标

访问 `/metrics` 端点获取监控指标：

```bash
curl http://your-domain:8000/metrics
```

可用指标：
- `http_server_requests_count` - 请求总数
- `http_server_requests_duration_seconds` - 请求延迟
- `http_server_requests_exceptions_total` - 异常总数

### 6.2 日志

日志文件位置：`./logs/`

- `server_YYYY-MM-DD.log` - 应用日志
- 自动按天切割
- 保留 30 天

查看实时日志：

```bash
tail -f logs/server_$(date +%Y-%m-%d).log
```

Docker 环境查看日志：

```bash
docker-compose logs -f tuchuang
```

---

## 7. 备份

### 7.1 需要备份的内容

- `data/files.db` - 数据库文件
- `uploads/` - 本地存储的文件
- `.env` - 配置文件（包含敏感信息）

### 7.2 备份脚本示例

```bash
#!/bin/bash
BACKUP_DIR="/backup/tuchuang"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# 备份数据库
cp data/files.db $BACKUP_DIR/files_$DATE.db

# 备份上传文件
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz uploads/

# 保留最近 7 天的备份
find $BACKUP_DIR -name "*.db" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
```

---

## 8. 故障排查

### 8.1 服务无法启动

```bash
# 检查配置文件语法
uv run python -c "from app.core.config import Config; print(Config)"

# 检查数据库
uv run python -c "import aiosqlite; import asyncio; asyncio.run(aiosqlite.connect('data/files.db'))"
```

### 8.2 数据库锁定

SQLite 不支持多进程写入，确保只运行一个 worker：

```bash
# 错误示例
uvicorn main:app --workers 4  # ❌ 会锁死

# 正确示例
uvicorn main:app --workers 1  # ✅ 单 worker
```

### 8.3 OSS 连接失败

- 检查网络连接：`ping oss-cn-hangzhou.aliyuncs.com`
- 验证凭证：确认 `OSS_AK` 和 `OSS_SK` 正确
- 检查 Bucket 确保存在且有权限

### 8.4 限流不生效

- 确认 `REDIS_URL` 配置正确
- 测试 Redis 连接：`redis-cli -u REDIS_URL ping`

### 8.5 配置热重载不生效

- 检查日志中是否有 "配置文件监听已启动" 的提示
- 确认 `.env` 文件路径正确
- 检查文件权限是否可读

---

## 9. 安全建议

1. **HTTPS** - 生产环境务必使用 HTTPS
2. **API Key** - 使用强随机密钥，定期更换
3. **CORS** - 限制允许的来源，不要使用 `*`
4. **加密** - 敏感数据启用文件加密
5. **备份** - 定期备份数据库和文件
6. **日志** - 保护日志文件，避免泄露敏感信息
7. **更新** - 及时更新依赖包，修复安全漏洞
