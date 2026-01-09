# Docker 部署说明

本目录包含图床服务的 Docker 配置文件。

---

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| `Dockerfile.backend` | 后端服务镜像构建文件 |
| `Dockerfile.frontend` | 前端管理后台镜像构建文件 |

---

## 🚀 启动方式

项目根目录提供了三种 Docker Compose 配置文件：

### 1️⃣ 完整启动（前后端）

```bash
docker-compose up -d --build
```

启动服务：
- 后端 API: http://localhost:8000
- 前端管理: http://localhost:3000

### 2️⃣ 仅启动后端

```bash
docker-compose -f docker-compose.backend.yml up -d --build
```

仅启动后端 API: http://localhost:8000

### 3️⃣ 仅启动前端

```bash
docker-compose -f docker-compose.frontend.yml up -d --build
```

仅启动前端管理: http://localhost:3000

> 注意：单独启动前端时，需要设置环境变量 `NEXT_PUBLIC_API_URL` 指向后端地址

---

## 🛠️ 常用命令

| 命令 | 说明 |
|------|------|
| `docker-compose up -d --build` | 构建并启动所有服务 |
| `docker-compose -f docker-compose.backend.yml up -d --build` | 仅启动后端 |
| `docker-compose -f docker-compose.frontend.yml up -d --build` | 仅启动前端 |
| `docker-compose down` | 停止并删除所有服务 |
| `docker-compose logs -f` | 查看所有服务日志 |
| `docker-compose logs -f tuchuang` | 查看后端服务日志 |
| `docker-compose logs -f admin` | 查看前端服务日志 |
| `docker-compose restart` | 重启所有服务 |
| `docker-compose ps` | 查看服务状态 |
| `docker-compose exec tuchuang bash` | 进入后端容器 |
| `docker-compose exec admin sh` | 进入前端容器 |

---

## 🔧 环境变量配置

在项目根目录创建 `.env` 文件，配置以下变量：

```bash
# 基础配置
HOST_DOMAIN=http://localhost:8000

# 鉴权配置
AUTH_ENABLED=true
API_KEY=your-secret-key

# 加密配置
ENCRYPTION_ENABLED=true
ENCRYPTION_KEY=your-encryption-key

# ... 更多配置见 .env.example
```

前端环境变量（仅单独启动前端时需要）：

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_KEY=your-api-key
```

---

## 📊 服务端口

| 服务 | 容器名 | 端口 |
|------|--------|------|
| 后端 API | tuchuang_server | 8000 |
| 前端管理 | tuchuang_admin | 3000 |

---

## 💾 数据持久化

### 数据卷

| 卷名 | 用途 |
|------|------|
| `tuchuang_db` | 数据库持久化（命名卷） |

### 目录挂载

| 目录 | 用途 |
|------|------|
| `./uploads` | 本地存储目录 |
| `./logs` | 日志目录 |

---

## 🏥 健康检查

### 后端

```bash
curl http://localhost:8000/health
```

### 前端

```bash
curl http://localhost:3000
```

---

## 🔄 更新部署

### 重新构建并启动

```bash
docker-compose up -d --build
```

### 仅重新构建镜像

```bash
docker-compose build
docker-compose up -d
```

### 查看构建日志

```bash
docker-compose up --build
```
