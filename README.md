# 🚀 图床服务 (Tuchuang File Server)

一个**企业级、高安全、高性能**的文件直链托管服务。

专为 JSON 配置文件的分发设计，具备**透明加解密**、**即时压缩**、**哈希去重**、**混合存储**、**配置热重载**和**全链路监控**能力。

> ✨ **高度模块化**：所有高级特性（加密、压缩、鉴权、Redis、OSS）均为**可选配置**，通过 `.env` 文件按需开启。
>
> 🔄 **配置热重载**：修改 `.env` 文件后无需重启服务，配置自动生效。

---

## 🌟 核心特性

### 1. 🔒 安全特性 [可选]

| 功能 | 说明 |
|------|------|
| **静态加密** | Fernet (AES-128) 算法加密存储，服务器沦陷也能保护数据 |
| **动态解密** | 下载时实时解密，内存流式传输，无明文临时文件 |
| **内容校验** | 强制解析 JSON 格式，拒绝非法文件 |
| **API 鉴权** | 支持 API Key 验证，保护上传接口 |
| **文件大小限制** | 可配置最大文件大小（默认 10MB） |
| **CORS 控制** | 可配置允许的跨域来源 |

### 2. ⚡ 性能优化 [可选]

| 功能 | 说明 |
|------|------|
| **orjson** | 高性能 JSON 解析，比标准库快 5-10 倍 |
| **Gzip 压缩** | 可配置压缩等级（1-9），节省高达 80% 空间 |
| **哈希去重** | BLAKE2b 指纹识别（比 MD5 更快更安全），实现"秒传"功能 |
| **TTL 缓存** | 文件元数据缓存（5分钟过期），减少数据库查询 |
| **aiosqlite** | 全异步数据库，无阻塞操作 |
| **HTTP 复用** | 全局异步 HTTP 客户端，复用 TCP 连接 |
| **安全随机 ID** | 使用 `secrets.token_hex` 生成文件 ID，更安全 |

### 3. 🧠 混合架构 [可选]

| 功能 | 说明 |
|------|------|
| **双重存储** | 本地磁盘 + 阿里云 OSS 双写 |
| **混合限流** | 内存限流 或 Redis 分布式限流 |
| **生命周期** | 支持 1天/7天/1月/永久，过期自动清理 |

### 4. 📊 可观测性 [默认开启]

| 功能 | 说明 |
|------|------|
| **Prometheus** | `/metrics` 端点暴露 QPS、延迟、错误率 |
| **健康检查** | `/health` 端点返回各组件状态 |
| **结构化日志** | Loguru 日志，自动轮转、保留 30 天 |

### 5. 🔄 运维特性

| 功能 | 说明 |
|------|------|
| **配置热重载** | 修改 `.env` 后自动生效，无需重启服务 |
| **文件同步** | 定期扫描并清理磁盘上已删除的文件记录 |
| **Web 管理界面** | Next.js 构建的现代化管理后台 |
| **Docker 部署** | 支持完整部署、独立后端、独立前端三种模式 |

### 6. 🔧 技术栈

| 组件 | 后端技术 | 前端技术 |
|------|---------|---------|
| **Web 框架** | FastAPI + Uvicorn | Next.js 14 |
| **数据库** | SQLite (aiosqlite 异步) | - |
| **JSON 处理** | orjson | - |
| **加密** | cryptography (Fernet) | - |
| **缓存** | cachetools (TTL) | TanStack Query |
| **日志** | loguru | - |
| **监控** | prometheus-fastapi-instrumentator | - |
| **UI 组件** | - | Radix UI + Tailwind CSS |
| **图表** | - | Recharts |

---

## 📂 目录结构

```text
tuchuang/
├── app/                          # 后端 Python 应用
│   ├── __init__.py
│   ├── api.py                    # 🛣️ API 路由
│   ├── models.py                 # 📦 Pydantic 数据模型
│   ├── services.py               # ⚙️ 核心业务逻辑
│   ├── database.py               # 🗄️ 异步数据库
│   ├── exceptions.py             # ⚠️ 自定义异常
│   ├── config_manager.py         # 🔧 配置管理器
│   └── core/
│       ├── config.py             # ⚙️ 配置管理（支持热重载）
│       ├── crypto.py             # 🔐 加解密引擎
│       ├── http_client.py        # 🌐 HTTP 客户端
│       ├── logger.py             # 📝 日志配置
│       ├── oss_client.py         # ☁️ OSS 客户端
│       ├── security.py           # 🚦 限流与鉴权
│       ├── config_watcher.py     # 👁️ 文件监听器
│       └── config_reloader.py    # 🔄 配置重载协调器
│
├── admin/                        # 🎨 前端管理界面 (Next.js)
│   ├── app/                      # Next.js App Router
│   │   ├── page.tsx              # 📊 仪表盘主页
│   │   ├── files/                # 📁 文件管理
│   │   ├── stats/                # 📈 统计分析
│   │   └── settings/             # ⚙️ 系统设置
│   ├── components/               # UI 组件
│   │   ├── ui/                   # 基础组件 (Radix UI)
│   │   └── dashboard/            # 仪表盘组件
│   └── lib/                      # 工具库
│       ├── api/                  # API 客户端
│       ├── hooks/                # React Hooks
│       ├── query-keys.ts         # Query Keys
│       └── types/                # TypeScript 类型
│
├── docker/                       # 🐳 Docker 配置
│   ├── Dockerfile.backend        # 后端镜像
│   ├── Dockerfile.frontend       # 前端镜像
│   └── README.md                 # Docker 部署说明
│
├── docs/                         # 📚 文档
│   ├── DEPLOYMENT.md             # 部署指南
│   ├── ERROR_CODES.md            # 错误码文档
│   └── TROUBLESHOOTING.md         # 故障排查
│
├── static/                       # 静态资源
├── uploads/                      # 本地存储目录
├── logs/                         # 运行日志
│
├── .env                          # ⚙️ 配置文件
├── .env.example                  # 📄 配置示例
├── pyproject.toml                # 📦 Python 依赖
├── docker-compose.yml            # 🐳 完整部署（前后端）
├── docker-compose.backend.yml    # 🐳 仅后端
├── docker-compose.frontend.yml   # 🐳 仅前端
└── main.py                       # 🚀 应用入口
```

---

## 📚 文档导航

| 文档 | 说明 |
|------|------|
| [部署指南](docs/DEPLOYMENT.md) | 生产环境部署、监控、备份、安全建议 |
| [错误码文档](docs/ERROR_CODES.md) | HTTP 状态码、业务错误码、错误响应格式 |
| [故障排查](docs/TROUBLESHOOTING.md) | 常见问题及解决方案 |
| [Docker 部署](docker/README.md) | Docker 部署详细说明 |

---

## 🛠️ 快速部署

### 方式 A: Docker 完整部署 (推荐)

```bash
# 1. 克隆项目
git clone <repo_url>
cd tuchuang

# 2. 复制配置文件
cp .env.example .env

# 3. 生成加密密钥（如需开启加密）
docker run --rm python:3.12 python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 4. 编辑 .env，填入必要配置
# HOST_DOMAIN=http://your-domain:8000
# ENCRYPTION_KEY=生成的密钥

# 5. 启动服务（前后端）
docker-compose up -d --build
```

服务启动后访问：
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs
- 前端管理: http://localhost:3000

### 方式 B: Docker 分别部署

```bash
# 仅启动后端
docker-compose -f docker-compose.backend.yml up -d --build

# 仅启动前端
docker-compose -f docker-compose.frontend.yml up -d --build
```

### 方式 C: 本地部署

#### 后端

```bash
# 1. 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 安装依赖
uv sync

# 3. 复制配置文件
cp .env.example .env

# 4. 启动服务
uv run main.py
```

#### 前端

```bash
# 1. 进入 admin 目录
cd admin

# 2. 安装依赖
npm install

# 3. 配置环境变量
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# 4. 启动开发服务器
npm run dev
```

---

## ⚙️ 配置说明 (.env)

所有配置通过 `.env` 文件控制，支持**热重载**，修改后自动生效。

### 基础配置 [必填]

| 变量 | 说明 | 示例 |
|------|------|------|
| `HOST_DOMAIN` | 服务对外域名/IP，用于生成直链 | `http://127.0.0.1:8000` |

### 安全配置 [可选]

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AUTH_ENABLED` | `false` | 是否开启 API Key 鉴权 |
| `API_KEY` | `secret` | 鉴权密钥 |
| `ENCRYPTION_ENABLED` | `false` | 是否开启文件加密 |
| `ENCRYPTION_KEY` | - | Fernet 密钥（开启加密时必填） |
| `MAX_FILE_SIZE` | `10485760` | 文件大小限制（字节，默认 10MB） |
| `CORS_ORIGINS` | `*` | CORS 允许来源（逗号分隔） |

### 性能配置 [可选]

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `COMPRESSION_ENABLED` | `false` | 是否开启 Gzip 压缩 |
| `COMPRESSION_LEVEL` | `6` | 压缩等级（1-9） |
| `RATE_LIMIT` | `60/minute` | 限流规则 |
| `REDIS_URL` | - | Redis 地址（留空使用内存限流） |

### OSS 云存储 [可选]

| 变量 | 说明 |
|------|------|
| `ENABLE_OSS` | 是否启用 OSS |
| `OSS_ENDPOINT` | OSS Endpoint（如：oss-cn-hangzhou.aliyuncs.com） |
| `OSS_BUCKET` | Bucket 名称 |
| `OSS_AK` | AccessKey ID |
| `OSS_SK` | AccessKey Secret |
| `OSS_DOMAIN` | OSS 公网访问域名 |

---

## 🔌 API 接口文档

### 1. 上传文件

```bash
POST /upload
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | 是 | JSON 文件 |
| `time_limit` | String | 否 | 有效期：`1d` / `7d` / `1m` / `perm` |

**请求头（鉴权开启时）：**
```
x-api-key: your-secret-key
```

**响应示例：**
```json
{
  "code": 200,
  "msg": "✅ 上传成功",
  "data": {
    "url": "http://127.0.0.1:8000/f/a1b2c3d4",
    "filename": "config.json",
    "expiry": "永久",
    "is_duplicate": false
  }
}
```

### 2. 获取文件

```bash
GET /f/{file_id}
```

自动处理：`读取磁盘 → 解密 (AES) → 解压 (Gzip) → 返回 JSON`

### 3. 健康检查

```bash
GET /health
```

**响应示例：**
```json
{
  "status": "🟢 健康",
  "version": "1.0.0",
  "components": {
    "database": "🟢 正常",
    "encryption": "🟢 已启用",
    "compression": "🟢 已启用",
    "oss": "🔴 未启用",
    "redis": "🔴 未启用"
  }
}
```

### 4. Prometheus 指标

```bash
GET /metrics
```

Prometheus 格式的监控指标。

---

## 📱 Legado (阅读) 适配

配置 JSON：

```json
{
  "summary": "图床服务",
  "uploadUrl": "http://your-domain:8000/upload,{\"method\":\"POST\",\"type\":\"multipart/form-data\",\"body\":{\"file\":\"fileRequest\",\"time_limit\":\"perm\"},\"headers\":{\"x-api-key\":\"your-key\"}}",
  "downloadUrlRule": "$.data.url",
  "compress": false
}
```

**说明：**
- 修改 `your-domain` 为实际地址
- 如开启鉴权，修改 `x-api-key` 为实际密钥
- `time_limit`: `1d`(1天) / `7d`(7天) / `1m`(1月) / `perm`(永久)

---

## 🏗️ 工作流程

### 写入流程

```
接收文件
  → 大小检查
  → 后缀名校验
  → JSON 校验与压缩
  → BLAKE2b 哈希计算
  → [去重检查 → 秒传]
  → Gzip 压缩 (可选)
  → Fernet 加密 (可选)
  → 本地存储
  → OSS 上传 (可选)
  → 写入元数据
```

### 读取流程

```
查询数据库
  → 读取本地文件
  → Fernet 解密 (如加密)
  → Gzip 解压 (如压缩)
  → 返回 JSON
```

---

## 🔄 运维特性

### 配置热重载

修改 `.env` 文件后，配置会自动重载，无需重启服务：

```bash
# 修改配置
vim .env

# 1 秒内自动生效
# 查看日志确认
tail -f logs/server_$(date +%Y-%m-%d).log
```

### 文件同步

后台任务每 30 秒扫描一次，自动清理磁盘上已删除的文件记录。

### 自动清理

后台任务每小时清理一次过期文件。

---

## 📝 维护

- **自动清理**: 后台任务每小时清理过期文件
- **文件同步**: 每 30 秒同步文件状态
- **日志轮转**: `logs/` 目录，按天切割，保留 30 天
- **优雅关闭**: 支持信号处理，完成后台任务再退出

---

## 📄 许可证

MIT License
