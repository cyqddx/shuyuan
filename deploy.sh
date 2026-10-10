#!/usr/bin/env bash
# ============================================================
# 🚀 图床服务一键部署脚本 (单文件,Docker / systemd 双模式)
# ============================================================
# 命令 (默认 deploy):
#   deploy            部署或更新服务
#   stop              停止所有相关服务 (含监控栈)
#   restart           重启服务
#   status            查看运行状态
#   logs [目标]       跟踪日志 (目标: tuchuang|admin|mon,默认 tuchuang)
#   nginx             配置 Nginx 反向代理 + acme.sh 签发 HTTPS 证书并自动续期
#   clean             清除所有部署内容 (服务/容器/nginx/证书,含 certbot 残留)
#   help              显示本帮助
#
# 选项:
#   --docker          使用 Docker 部署 (默认 systemd 直跑,更省资源)
#   --backend-only    仅部署后端,跳过管理后台 (最省资源)
#   --monitoring      附加启动 Prometheus + Grafana 监控栈 (依赖 Docker)
#   --no-autostart    systemd 服务不设开机自启 (默认自启)
#
# 示例:
#   sudo ./deploy.sh                          # systemd: 后端+管理后台
#   sudo ./deploy.sh --docker                 # Docker:  后端+管理后台
#   sudo ./deploy.sh --backend-only           # systemd: 仅后端
#   sudo ./deploy.sh --docker --monitoring    # Docker + 监控栈
#   sudo ./deploy.sh --backend-only --monitoring
#   sudo ./deploy.sh nginx                   # 按 .env 中 NGINX_DOMAIN 配置反代+证书
#   sudo ./deploy.sh clean                   # 全部清除后重新初次部署
#   ./deploy.sh status
#   ./deploy.sh logs admin
#
# 端口统一在 .env 中配置:
#   APP_PORT (后端 8000) / ADMIN_PORT (后台 3000)
#   PROMETHEUS_PORT (9090) / GRAFANA_PORT (3001)
#   ⚠️ 修改 APP_PORT 后请同步修改 HOST_DOMAIN 中的端口
#
# 更新部署: git pull 后重新运行 deploy 即可
# 查看日志: ./deploy.sh logs
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"
APP_DIR=$(pwd)
VENV_BIN="$APP_DIR/.venv/bin"

CMD=deploy
MODE=""          # docker | "" (默认 systemd)
WITH_ADMIN=1
WITH_MON=0
AUTO_START=1
LOG_TARGET=""

usage() { awk 'NR>1{ if($0!~/^#/) exit; sub(/^# ?/,""); print }' "$0"; }

die() { echo "❌ $*" >&2; exit 1; }

# 依赖命令检测:缺失时给出安装命令并退出,不代替用户做安装决定
need_cmd() {
    local cmd=$1; shift
    command -v "$cmd" >/dev/null 2>&1 && return 0
    echo "❌ 缺少命令: $cmd" >&2
    printf '   %s\n' "$@" >&2
    die "请安装上述依赖后重跑本脚本"
}

# ---------- 权限 (仅 systemd 部署需要 root,只读命令不强制) ----------
init_sudo() {
    SUDO=""
    if [ "$(id -u)" != 0 ] && command -v sudo >/dev/null; then
        SUDO="sudo"
    fi
}

# 定位 acme.sh: PATH → 当前用户目录 → root 目录 (sudo 后 HOME 可能被重置)
find_acme_sh() {
    local acme c
    acme=$(command -v acme.sh 2>/dev/null || true)
    for c in "${HOME}/.acme.sh/acme.sh" "/root/.acme.sh/acme.sh"; do
        if [ -z "$acme" ] && [ -x "$c" ]; then acme="$c"; fi
    done
    echo "$acme"
}

# 删除已存在的路径并逐项记录 (文件/目录/glob 展开结果均可,不存在则跳过)
rm_logged() {
    local p
    for p in "$@"; do
        if [ -e "$p" ] || [ -L "$p" ]; then
            $SUDO rm -rf "$p"
            echo "  🗑  已删除: $p"
        fi
    done
}

# 应用开机自启设置 (AUTO_START 由 --no-autostart 决定)
set_autostart() {
    if [ "$AUTO_START" = 1 ]; then
        $SUDO systemctl enable "$1" > /dev/null 2>&1 || true
    else
        $SUDO systemctl disable "$1" > /dev/null 2>&1 || true
        echo "⚪ $1 开机自启已禁用 (--no-autostart)"
    fi
}

# 剥离误填的协议前缀与路径 (NGINX_* 需要是纯域名)
strip_url() {
    local s=$1
    s=${s#http://}; s=${s#https://}; s=${s%%/*}
    echo "$s"
}

# ---------- 读取 .env 配置 ----------
read_config() {
    if [ -f .env ]; then
        APP_PORT=$(grep -E '^APP_PORT=' .env | cut -d= -f2- || true)
        ADMIN_PORT=$(grep -E '^ADMIN_PORT=' .env | cut -d= -f2- || true)
        PROM_PORT=$(grep -E '^PROMETHEUS_PORT=' .env | cut -d= -f2- || true)
        GRAF_PORT=$(grep -E '^GRAFANA_PORT=' .env | cut -d= -f2- || true)
        NGINX_DOMAIN=$(grep -E '^NGINX_DOMAIN=' .env | cut -d= -f2- || true)
        NGINX_ADMIN_DOMAIN=$(grep -E '^NGINX_ADMIN_DOMAIN=' .env | cut -d= -f2- || true)
        NGINX_CERT_EMAIL=$(grep -E '^NGINX_CERT_EMAIL=' .env | cut -d= -f2- || true)
        NGINX_CERT_DIR=$(grep -E '^NGINX_CERT_DIR=' .env | cut -d= -f2- || true)
        MAX_FILE_SIZE=$(grep -E '^MAX_FILE_SIZE=' .env | cut -d= -f2- || true)
    fi
    APP_PORT=${APP_PORT:-8000}
    ADMIN_PORT=${ADMIN_PORT:-3000}
    PROM_PORT=${PROM_PORT:-9090}
    GRAF_PORT=${GRAF_PORT:-3001}
    MAX_FILE_SIZE=${MAX_FILE_SIZE:-10485760}
    NGINX_DOMAIN=$(strip_url "${NGINX_DOMAIN:-}")
    NGINX_ADMIN_DOMAIN=$(strip_url "${NGINX_ADMIN_DOMAIN:-}")
    NGINX_CERT_EMAIL=${NGINX_CERT_EMAIL:-}
    CERT_DIR=${NGINX_CERT_DIR:-/etc/nginx/ssl}   # acme.sh --install-cert 安装目录
}

# ============================================================
# 🧹 模式互斥清理 (切换部署方式 / 避免端口冲突)
# ============================================================
stop_systemd_if_running() {
    command -v systemctl >/dev/null 2>&1 || return 0
    $SUDO systemctl is-active --quiet tuchuang.service 2>/dev/null || return 0
    echo "⏳ 停止已有 systemd 部署..."
    $SUDO systemctl stop tuchuang.service tuchuang-admin.service 2>/dev/null || true
}

stop_docker_if_running() {
    command -v docker >/dev/null 2>&1 || return 0
    docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'tuchuang_server' || return 0
    echo "⏳ 停止已有 Docker 部署..."
    docker compose down --remove-orphans || true
}

# ============================================================
# 🐳 Docker 模式部署
# ============================================================
deploy_docker() {
    command -v docker >/dev/null || die "未安装 Docker"
    docker compose version >/dev/null 2>&1 || die "Docker Compose 不可用"
    stop_systemd_if_running

    local services=(tuchuang)
    if [ "$WITH_ADMIN" = 1 ]; then
        services+=(admin)
    else
        docker compose stop admin 2>/dev/null || true
    fi

    echo "🐳 Docker 部署..."
    docker compose up -d --build "${services[@]}"
}

# ============================================================
# 🖥️ systemd 模式部署
# ============================================================
deploy_systemd() {
    if [ -z "$SUDO" ] && [ "$(id -u)" != 0 ]; then
        die "systemd 部署需要 root,请用 sudo 运行"
    fi
    stop_docker_if_running

    # 依赖检测 (不自动安装,缺失时给出安装命令)
    need_cmd uv "curl -LsSf https://astral.sh/uv/install.sh | sh" \
        "装完执行: export PATH=\$HOME/.local/bin:\$PATH (或重开终端)"

    echo "📦 安装后端依赖 (按 uv.lock 锁定版本)..."
    uv sync --frozen --no-dev

    $SUDO tee /etc/systemd/system/tuchuang.service > /dev/null <<EOF
[Unit]
Description=Tuchuang file server
After=network.target

[Service]
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_BIN/uvicorn main:app --host 0.0.0.0 --port $APP_PORT --workers 1 --no-access-log
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

    # ---------- 管理后台 (Node 20+) ----------
    local with_admin=0
    if [ "$WITH_ADMIN" = 1 ]; then
        if command -v node >/dev/null 2>&1; then
            NODE_MAJOR=$(node -v | sed 's/^v//' | cut -d. -f1)
            if [ "$NODE_MAJOR" -lt 20 ]; then
                echo "⚠️  Node 版本过低 (需要 20+),跳过管理后台"
            else
                echo "📦 构建管理后台..."
                # NEXT_PUBLIC_* 是构建期内联到浏览器代码的,必须在 build 时注入
                HOST_DOMAIN_VAL=$(grep -E '^HOST_DOMAIN=' .env | cut -d= -f2-)
                API_KEY_VAL=$(grep -E '^API_KEY=' .env | cut -d= -f2-)
                (
                    cd admin
                    export NEXT_PUBLIC_API_URL="$HOST_DOMAIN_VAL" NEXT_PUBLIC_API_KEY="$API_KEY_VAL"
                    npm ci
                    npm run build
                )
                NPM_BIN=$(command -v npm)
                $SUDO tee /etc/systemd/system/tuchuang-admin.service > /dev/null <<EOF
[Unit]
Description=Tuchuang admin (Next.js)
After=network.target tuchuang.service

[Service]
WorkingDirectory=$APP_DIR/admin
Environment=NODE_ENV=production
Environment=PORT=$ADMIN_PORT
Environment=HOSTNAME=0.0.0.0
ExecStart=$NPM_BIN run start
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
                set_autostart tuchuang-admin.service
                with_admin=1
            fi
        else
            echo "⚪ 未检测到 Node.js,跳过管理后台 (需要时安装 Node 20+ 后重跑)"
        fi
    else
        # backend-only:停掉可能存在的旧 admin 服务
        $SUDO systemctl stop tuchuang-admin.service 2>/dev/null || true
        echo "⚪ 按参数跳过管理后台"
    fi

    echo "🚀 启动 systemd 服务..."
    $SUDO systemctl daemon-reload
    set_autostart tuchuang.service
    $SUDO systemctl restart tuchuang.service
    if [ "$with_admin" = 1 ]; then
        $SUDO systemctl restart tuchuang-admin.service
    fi
    WITH_ADMIN=$with_admin   # 汇总输出用
}

# ============================================================
# 📊 监控栈 (Prometheus + Grafana,始终走 Docker)
# ============================================================
start_monitoring() {
    if ! command -v docker >/dev/null 2>&1; then
        echo "⚠️  监控栈依赖 Docker,已跳过"
        return
    fi
    # 抓取目标端口同步为当前 APP_PORT
    # (systemd 模式下后端不在 Docker 网络中,靠 extra_hosts host-gateway 走宿主端口)
    sed -E -i.bak "s#tuchuang:[0-9]+#tuchuang:$APP_PORT#g" prometheus.yml && rm -f prometheus.yml.bak
    echo "📊 启动监控栈 (Prometheus + Grafana)..."
    docker compose -f docker-compose.monitoring.yml up -d
}

# ============================================================
# 🩺 健康检查 + 汇总
# ============================================================
health_check() {
    echo "⏳ 等待后端启动..."
    local ok=0
    for _ in $(seq 1 30); do
        curl -fsS -m 2 "http://127.0.0.1:$APP_PORT/health" >/dev/null 2>&1 && { ok=1; break; }
        sleep 2
    done
    [ "$ok" = 1 ] || die "60 秒内健康检查未通过 (日志: ./deploy.sh logs)"
    echo "✅ 部署完成"
    echo "   部署方式: $([ "$MODE" = docker ] && echo Docker || echo systemd)"
    echo "   后端:     http://127.0.0.1:$APP_PORT (docs: /docs)"
    if [ "$WITH_ADMIN" = 1 ]; then
        echo "   管理后台: http://127.0.0.1:$ADMIN_PORT"
    fi
    if [ "$WITH_MON" = 1 ]; then
        echo "   监控:     Prometheus :$PROM_PORT / Grafana :$GRAF_PORT (admin/admin)"
    fi
}

# ============================================================
# 🎛️ 命令实现
# ============================================================
cmd_deploy() {
    if [ ! -f .env ]; then
        cp .env.example .env
        echo "⚠️  已从 .env.example 生成 .env,请先编辑配置 (HOST_DOMAIN / API_KEY / 端口) 后重新运行"
        exit 1
    fi
    check_deploy_deps

    if [ "$MODE" = docker ]; then deploy_docker; else deploy_systemd; fi
    if [ "$WITH_MON" = 1 ]; then start_monitoring; fi
    health_check
}

# 健康检查依赖 curl,各模式部署前统一检测
check_deploy_deps() {
    need_cmd curl "Debian/Ubuntu: sudo apt-get install -y curl" "CentOS/RHEL: sudo yum install -y curl"
}

cmd_stop() {
    if command -v systemctl >/dev/null 2>&1; then
        $SUDO systemctl stop tuchuang.service tuchuang-admin.service 2>/dev/null || true
    fi
    if command -v docker >/dev/null 2>&1; then
        docker compose -f docker-compose.monitoring.yml down 2>/dev/null || true
        docker compose down --remove-orphans 2>/dev/null || true
    fi
    echo "✅ 已停止 (systemd 服务 + Docker 容器 + 监控栈)"
}

cmd_restart() {
    local did=0
    if command -v systemctl >/dev/null 2>&1 \
        && $SUDO systemctl is-active --quiet tuchuang.service 2>/dev/null; then
        $SUDO systemctl restart tuchuang.service
        if $SUDO systemctl is-active --quiet tuchuang-admin.service 2>/dev/null; then
            $SUDO systemctl restart tuchuang-admin.service
        fi
        did=1
        echo "✅ 已重启 systemd 服务"
    fi
    if command -v docker >/dev/null 2>&1 \
        && docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'tuchuang_server'; then
        docker compose restart
        did=1
        echo "✅ 已重启 Docker 容器"
    fi
    [ "$did" = 1 ] || echo "⚠️  未发现运行中的服务"
}

cmd_status() {
    echo "── systemd ──"
    if command -v systemctl >/dev/null 2>&1; then
        for u in tuchuang tuchuang-admin; do
            printf "  %-16s %s\n" "$u" "$($SUDO systemctl is-active "$u" 2>/dev/null || echo inactive)"
        done
    else
        echo "  (未安装 systemd)"
    fi
    echo "── docker ──"
    if command -v docker >/dev/null 2>&1; then
        docker compose ps 2>/dev/null | tail -n +2 || true
        docker compose -f docker-compose.monitoring.yml ps 2>/dev/null | tail -n +2 || true
    else
        echo "  (未安装 Docker)"
    fi
    echo "── 健康检查 ──"
    if curl -fsS -m 3 "http://127.0.0.1:$APP_PORT/health" >/dev/null 2>&1; then
        echo "  后端 ✓ http://127.0.0.1:$APP_PORT"
    else
        echo "  后端 ✗ 不可达"
    fi
    echo "── nginx ──"
    if command -v nginx >/dev/null 2>&1; then
        printf "  %-16s %s\n" "nginx" "$($SUDO systemctl is-active nginx 2>/dev/null || echo inactive)"
    else
        echo "  (未安装 nginx)"
    fi
}

cmd_logs() {
    local t=${LOG_TARGET:-tuchuang}
    if [ "$t" = mon ]; then
        command -v docker >/dev/null || die "监控栈依赖 Docker"
        exec docker compose -f docker-compose.monitoring.yml logs -f
    fi
    local unit=$([ "$t" = admin ] && echo tuchuang-admin || echo tuchuang)
    if command -v systemctl >/dev/null 2>&1 \
        && $SUDO systemctl is-active --quiet "$unit.service" 2>/dev/null; then
        exec $SUDO journalctl -u "$unit" -f
    fi
    command -v docker >/dev/null || die "服务未在运行"
    exec docker compose logs -f "$t"
}

# ============================================================
# 🌐 Nginx 反向代理 + HTTPS 证书 (Let's Encrypt,自动续期)
# ============================================================

# 通用反代头 (heredoc 内 nginx 变量需转义为 \$xxx)
PROXY_HEADERS='proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;'

# ACME http-01 webroot 验证 (acme.sh 依赖;80 上直通,续期不走 301)
ACME_LOCATION='location /.well-known/acme-challenge/ {
        root /var/www/html;
    }'

nginx_write_conf() {
    # $1: http | https (https 版含 301 跳转与 SSL 配置)
    local mode=$1 body
    # 上传大小限制对齐后端 MAX_FILE_SIZE (向上取整为 MB)
    body=$(awk "BEGIN{printf \"%dm\", int(($MAX_FILE_SIZE+1048575)/1048576)}")

    local ssl_server="" redirect="" acme_loc=""
    if [ "$mode" = https ]; then
        ssl_server="    ssl_certificate     $CERT_DIR/$NGINX_DOMAIN/fullchain.pem;
    ssl_certificate_key $CERT_DIR/$NGINX_DOMAIN/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    add_header Strict-Transport-Security \"max-age=31536000\" always;"
        redirect="server {
    listen 80;
    server_name $NGINX_DOMAIN;
$ACME_LOCATION
    location / {
        return 301 https://\$host\$request_uri;
    }
}

"
    else
        acme_loc="$ACME_LOCATION"
    fi

    $SUDO tee /etc/nginx/conf.d/tuchuang.conf > /dev/null <<EOF
# 图床后端 / 文件直链 (由 deploy.sh 生成,勿手改)
$redirect
server {
    $( [ "$mode" = https ] && echo 'listen 443 ssl http2;' || echo 'listen 80;' )
    server_name $NGINX_DOMAIN;

$ssl_server
    client_max_body_size $body;

$acme_loc
    location / {
        proxy_pass http://127.0.0.1:$APP_PORT;
        $PROXY_HEADERS
    }
}
EOF

    if [ -n "$NGINX_ADMIN_DOMAIN" ]; then
        local redirect_admin="" acme_loc_admin=""
        if [ "$mode" = https ]; then
            redirect_admin="server {
    listen 80;
    server_name $NGINX_ADMIN_DOMAIN;
$ACME_LOCATION
    location / {
        return 301 https://\$host\$request_uri;
    }
}

"
        else
            acme_loc_admin="$ACME_LOCATION"
        fi
        $SUDO tee /etc/nginx/conf.d/tuchuang-admin.conf > /dev/null <<EOF
# 图床管理后台 (由 deploy.sh 生成,勿手改)
$redirect_admin
server {
    $( [ "$mode" = https ] && echo 'listen 443 ssl http2;' || echo 'listen 80;' )
    server_name $NGINX_ADMIN_DOMAIN;

$ssl_server
$acme_loc_admin
    location / {
        proxy_pass http://127.0.0.1:$ADMIN_PORT;
        $PROXY_HEADERS
    }
}
EOF
    fi
}

nginx_reload() {
    $SUDO nginx -t || die "nginx 配置校验失败"
    $SUDO systemctl reload nginx
}

cmd_nginx() {
    if [ -z "$SUDO" ] && [ "$(id -u)" != 0 ]; then
        die "nginx 配置需要 root,请用 sudo 运行"
    fi
    [ -n "$NGINX_DOMAIN" ] || die "请先在 .env 中配置 NGINX_DOMAIN (管理后台域名用 NGINX_ADMIN_DOMAIN)"

    # ---------- 1. 依赖检测 (缺失时提示安装命令,不代替用户安装) ----------
    need_cmd nginx \
        "Debian/Ubuntu: sudo apt-get install -y nginx" \
        "CentOS/RHEL:   sudo yum install -y nginx"
    local acme_sh
    acme_sh=$(find_acme_sh)
    [ -n "$acme_sh" ] || die "未找到 acme.sh,请先安装: curl https://get.acme.sh | sh -s email=<邮箱>"

    # ---------- 2. 先上 HTTP 配置 (供 ACME 域名验证) ----------
    echo "🌐 生成 HTTP 配置..."
    nginx_write_conf http
    $SUDO systemctl enable --now nginx > /dev/null 2>&1 || true
    $SUDO mkdir -p /var/www/html
    nginx_reload

    # ---------- 3. acme.sh 签发 (SAN: 主域+管理域;--force 覆盖上次失败残留的 domain key) ----------
    local cert_file="$CERT_DIR/$NGINX_DOMAIN/fullchain.pem"
    if [ -f "$cert_file" ]; then
        echo "🔒 证书已存在,沿用 (重签请先删除 $CERT_DIR/$NGINX_DOMAIN)"
    else
        echo "🔒 签发 Let's Encrypt 证书 (acme.sh)..."
        local dargs=(--issue -d "$NGINX_DOMAIN" -w /var/www/html
            --server letsencrypt --keylength ec-256 --force)
        if [ -n "$NGINX_ADMIN_DOMAIN" ]; then dargs+=(-d "$NGINX_ADMIN_DOMAIN"); fi
        if [ -n "$NGINX_CERT_EMAIL" ]; then dargs+=(-m "$NGINX_CERT_EMAIL"); fi
        $SUDO "$acme_sh" "${dargs[@]}" || die "证书申请失败 (确认域名 DNS 已指向本机且 80 端口可访问)"

        echo "📦 安装证书到 $CERT_DIR/$NGINX_DOMAIN ..."
        $SUDO mkdir -p "$CERT_DIR/$NGINX_DOMAIN"
        $SUDO "$acme_sh" --install-cert -d "$NGINX_DOMAIN" --ecc \
            --fullchain-file "$cert_file" \
            --key-file "$CERT_DIR/$NGINX_DOMAIN/privkey.pem" \
            --reloadcmd "nginx -t && systemctl reload nginx" \
            || die "证书安装失败"
    fi

    # ---------- 4. 替换为 HTTPS 配置 ----------
    echo "🔐 启用 HTTPS..."
    nginx_write_conf https
    nginx_reload

    # ---------- 5. 续期 ----------
    echo "⏰ 续期: acme.sh cron 自动执行,续期后自动 reload nginx (查看: sudo $acme_sh --list)"

    echo "✅ Nginx + HTTPS 配置完成"
    echo "   直链/后端:  https://$NGINX_DOMAIN"
    if [ -n "$NGINX_ADMIN_DOMAIN" ]; then
        echo "   管理后台:   https://$NGINX_ADMIN_DOMAIN"
    fi
    echo "   ⚠️ 请将 .env 中 HOST_DOMAIN 改为 https://$NGINX_DOMAIN 后重新 deploy"
    echo "      (生成直链和管理后台 API 地址都会随之使用 HTTPS)"
}

# ============================================================
# 🧹 clean: 清除所有部署内容 (重新初次部署前用)
# ============================================================
cmd_clean() {
    if [ -z "$SUDO" ] && [ "$(id -u)" != 0 ]; then
        die "清理需要 root,请用 sudo 运行"
    fi
    echo "⚠️  将删除以下内容:"
    echo "  - systemd 服务: tuchuang.service / tuchuang-admin.service"
    echo "  - Docker 容器:  应用栈 + 监控栈 (镜像/卷/uploads 数据保留)"
    echo "  - nginx 配置:   /etc/nginx/conf.d/tuchuang.conf / tuchuang-admin.conf"
    if [ -n "$NGINX_DOMAIN" ]; then
        echo "  - 证书:         $CERT_DIR 下的域名证书 + acme.sh 域名数据 + certbot 残留"
    fi
    echo "  (保留 .env / uploads / 数据库等应用数据)"
    read -rp "确认清理?输入 yes 继续: " REPLY
    [ "$REPLY" = yes ] || { echo "⚪ 已取消"; exit 0; }

    echo "🧹 开始清理,实际删除项:"
    cmd_stop
    rm_logged /etc/systemd/system/tuchuang.service /etc/systemd/system/tuchuang-admin.service
    if command -v systemctl >/dev/null 2>&1; then
        $SUDO systemctl daemon-reload
        echo "  已执行 systemctl daemon-reload"
    fi
    rm_logged /etc/nginx/conf.d/tuchuang.conf /etc/nginx/conf.d/tuchuang-admin.conf
    if command -v nginx >/dev/null 2>&1 && $SUDO nginx -t >/dev/null 2>&1; then
        $SUDO systemctl reload nginx 2>/dev/null || true
    fi

    # 证书: acme.sh 移除管理 (--remove 不吊销,LE 证书自然过期) + 删全部相关文件
    if [ -n "$NGINX_DOMAIN" ]; then
        local acme_sh
        acme_sh=$(find_acme_sh)
        if [ -n "$acme_sh" ]; then
            $SUDO "$acme_sh" --remove -d "$NGINX_DOMAIN" >/dev/null 2>&1 || true
            if [ -n "$NGINX_ADMIN_DOMAIN" ]; then
                $SUDO "$acme_sh" --remove -d "$NGINX_ADMIN_DOMAIN" >/dev/null 2>&1 || true
            fi
        fi
        local domains=("$NGINX_DOMAIN")
        if [ -n "$NGINX_ADMIN_DOMAIN" ]; then domains+=("$NGINX_ADMIN_DOMAIN"); fi
        local d
        for d in "${domains[@]}"; do
            rm_logged "$CERT_DIR/$d" \
                      "${HOME}/.acme.sh/${d}_ecc" "${HOME}/.acme.sh/${d}" \
                      "/root/.acme.sh/${d}_ecc" "/root/.acme.sh/${d}" \
                      "/etc/letsencrypt/live/$d" "/etc/letsencrypt/archive/$d" \
                      "/etc/letsencrypt/renewal/$d.conf"
        done
        # certbot 残留 (历史部署用 certbot 时遗留)
        if command -v certbot >/dev/null 2>&1; then
            if $SUDO systemctl is-enabled certbot.timer >/dev/null 2>&1; then
                $SUDO systemctl disable --now certbot.timer
                echo "  已停用: certbot.timer"
            fi
            if [ -d "/etc/letsencrypt/live/$NGINX_DOMAIN" ]; then
                $SUDO certbot delete --cert-name "$NGINX_DOMAIN" --non-interactive >/dev/null 2>&1 || true
            fi
        fi
        rm_logged /etc/cron.d/certbot-renew
    fi

    echo "✅ 清理完成,重新部署: sudo ./deploy.sh && sudo ./deploy.sh nginx"
}

# ============================================================
# 🎬 参数解析 + 分发
# ============================================================
for arg in "$@"; do
    case $arg in
        deploy|stop|restart|status|logs|nginx|clean|help) CMD=$arg ;;
        --docker|-d)          MODE=docker ;;
        --systemd)            MODE=systemd ;;
        --backend-only)       WITH_ADMIN=0 ;;
        --monitoring|-m)      WITH_MON=1 ;;
        --no-autostart)       AUTO_START=0 ;;
        tuchuang|admin|mon)   LOG_TARGET=$arg ;;
        --help|-h)            CMD=help ;;
        *) die "未知参数: $arg (查看帮助: ./deploy.sh help)" ;;
    esac
done

init_sudo
read_config

case $CMD in
    deploy)  cmd_deploy ;;
    stop)    cmd_stop ;;
    restart) cmd_restart ;;
    status)  cmd_status ;;
    logs)    cmd_logs ;;
    nginx)   cmd_nginx ;;
    clean)   cmd_clean ;;
    help)    usage ;;
esac
