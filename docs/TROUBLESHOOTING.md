# 图床服务 - 常见问题排查指南

本文档记录图床服务部署和运行过程中遇到的常见问题及解决方案。

---

## 🐳 Docker 相关问题

### 问题：Docker Hub 连接超时

**错误信息：**
```
failed to solve: DeadlineExceeded: python:3.12-slim: failed to resolve source metadata for docker.io/library/python:3.12-slim:
failed to do request: Head "https://registry-1.docker.io/v2/library/python/manifests/3.12-slim":
dial tcp 108.160.163.112:443: i/o timeout
```

**原因：**
Docker Hub (`registry-1.docker.io`) 在某些网络环境下访问受限或速度极慢，导致镜像拉取超时。

**解决方案：**
配置 Docker 国内镜像加速源。

1. 编辑 Docker 配置文件：
```bash
sudo tee /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": [
    "https://docker.1panel.live",
    "https://dockerhub.icu",
    "https://docker.chenby.cn"
  ]
}
EOF
```

2. 重启 Docker 服务：
```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
```

3. 验证配置：
```bash
docker info | grep -A5 "Registry Mirrors"
```

---

## 🔍 常用排查命令

### 查看容器状态
```bash
docker compose ps
```

### 查看容器日志
```bash
# 查看最近 30 行日志
docker logs tuchuang_server --tail 30

# 实时跟踪日志
docker logs tuchuang_server -f
```

### 重新构建并启动
```bash
docker compose up -d --build
```

### 进入容器调试
```bash
docker exec -it tuchuang_server bash
```

### 检查 Docker 镜像源配置
```bash
docker info | grep -A5 "Registry Mirrors"
```

---

## 📝 其他注意事项

### 网络问题排查
如果遇到镜像拉取问题，可以尝试：
1. 检查网络连接是否正常
2. 尝试手动拉取镜像：`docker pull <镜像名>`
3. 更换不同的镜像源

### 健康检查失败
容器状态显示 `unhealthy` 时：
1. 检查端口 8000 是否被占用
2. 查看容器日志排查启动错误
3. 确认 `.env` 配置正确

### 数据持久化
确保以下目录和卷正确挂载：
- `./uploads` → 上传文件存储（绑定挂载）
- `tuchuang_db` → SQLite 数据库（命名卷，存放在 `/app/data/`）
- `./logs` → 应用日志（绑定挂载）

**数据库备份：**
```bash
# 从命名卷复制数据库到本地
docker cp tuchuang_server:/app/data/files.db ./files_backup.db

# 恢复数据库
docker cp ./files_backup.db tuchuang_server:/app/data/files.db
```
