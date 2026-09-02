#!/usr/bin/env bash
set -Eeuo pipefail

IMAGE="${IMAGE:-ghcr.io/robin0822/test-api:latest}"
DEPLOY_DIR="${DEPLOY_DIR:-/opt/test-api}"
SERVER_NAME="${SERVER_NAME:-172.29.231.119}"
HOST_PORT="${HOST_PORT:-13000}"
NGINX_CONF="${NGINX_CONF:-/etc/nginx/conf.d/test-api.conf}"
COMPOSE_URL="${COMPOSE_URL:-https://raw.githubusercontent.com/robin0822/test-api/main/compose.yaml}"

log() { printf '[test-api] %s\n' "$*"; }
fail() { printf '[test-api] ERROR: %s\n' "$*" >&2; exit 1; }
random_value() { tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32 || true; }

[[ "${EUID}" -eq 0 ]] || fail '请使用 root 用户运行部署脚本'
for command in docker nginx curl; do command -v "${command}" >/dev/null || fail "未安装 ${command}"; done
docker compose version >/dev/null || fail '未安装 Docker Compose v2'

install -d -m 0750 "${DEPLOY_DIR}"
log '下载 Docker Compose 配置'
curl -fsSL "${COMPOSE_URL}" -o "${DEPLOY_DIR}/compose.yaml"

if [[ ! -f "${DEPLOY_DIR}/.env" ]]; then
  log '创建首次部署环境配置（模型使用 Mock，配置新 Key 后再关闭）'
  cat >"${DEPLOY_DIR}/.env" <<EOF
IMAGE=${IMAGE}
HOST_PORT=${HOST_PORT}
POSTGRES_IMAGE=postgres:16-alpine
REDIS_IMAGE=redis:7-alpine
POSTGRES_PASSWORD=$(random_value)
API_TOKEN=$(random_value)
MODEL_API_BASE=https://maas-api.cn-huabei-1.xf-yun.com/v2
MODEL_API_KEY=
MODEL_ID=xopkimik26
MODEL_TEMPERATURE=0.3
MODEL_MAX_TOKENS=4096
MODEL_CHUNK_CHARS=30000
MODEL_MOCK=true
EOF
  chmod 0600 "${DEPLOY_DIR}/.env"
fi

cd "${DEPLOY_DIR}"
log '移除旧版单容器（如果存在）'
if docker ps -a --format '{{.Names}}' | grep -qx test-api; then
  existing_project="$(docker inspect test-api --format '{{index .Config.Labels "com.docker.compose.project"}}' 2>/dev/null || true)"
  if [[ "${existing_project}" != "test-api" ]]; then
    docker rm -f test-api >/dev/null
  fi
fi

log '拉取 ARM64 应用和基础设施镜像'
docker compose pull
log '启动 API、Worker、PostgreSQL、Redis'
docker compose up -d --remove-orphans

log '等待 API 健康检查'
for attempt in {1..60}; do
  curl -fsS "http://127.0.0.1:${HOST_PORT}/health" >/dev/null && break
  [[ "${attempt}" -lt 60 ]] || { docker compose ps; docker compose logs --tail=100 api; fail 'API 健康检查失败'; }
  sleep 2
done

log '配置宿主机 Nginx'
tmp_conf="$(mktemp)"
trap 'rm -f "${tmp_conf}"' EXIT
cat >"${tmp_conf}" <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name ${SERVER_NAME};
    client_max_body_size 210m;
    proxy_connect_timeout 10s;
    proxy_read_timeout 300s;

    location / {
        proxy_pass http://127.0.0.1:${HOST_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        add_header Cache-Control "no-store" always;
    }
}
EOF
install -m 0644 "${tmp_conf}" "${NGINX_CONF}"
nginx -t
systemctl reload nginx

log '最终检查'
curl -fsS -H "Host: ${SERVER_NAME}" http://127.0.0.1/health
docker compose ps
log "部署成功：http://${SERVER_NAME}/docs"
log "环境配置：${DEPLOY_DIR}/.env"
