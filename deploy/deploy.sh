#!/usr/bin/env bash
set -Eeuo pipefail

IMAGE="${IMAGE:-ghcr.io/robin0822/test-api:latest}"
CONTAINER_NAME="${CONTAINER_NAME:-test-api}"
HOST_PORT="${HOST_PORT:-13000}"
SERVER_NAME="${SERVER_NAME:-172.29.231.119}"
NGINX_CONF="${NGINX_CONF:-/etc/nginx/conf.d/test-api.conf}"

log() { printf '[test-api] %s\n' "$*"; }
fail() { printf '[test-api] ERROR: %s\n' "$*" >&2; exit 1; }

[[ "${EUID}" -eq 0 ]] || fail '请使用 root 用户运行部署脚本'
command -v docker >/dev/null || fail '未安装 Docker'
command -v nginx >/dev/null || fail '未安装 Nginx'
command -v curl >/dev/null || fail '未安装 curl'

if [[ -n "${GHCR_TOKEN:-}" ]]; then
  [[ -n "${GHCR_USERNAME:-}" ]] || fail '设置 GHCR_TOKEN 时必须同时设置 GHCR_USERNAME'
  log '登录 GHCR'
  printf '%s' "${GHCR_TOKEN}" | docker login ghcr.io -u "${GHCR_USERNAME}" --password-stdin
fi

log "拉取镜像 ${IMAGE}"
docker pull "${IMAGE}"

log '启动新容器'
docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
docker run -d \
  --name "${CONTAINER_NAME}" \
  --restart unless-stopped \
  --pull never \
  -p "127.0.0.1:${HOST_PORT}:8080" \
  "${IMAGE}" >/dev/null

log '等待容器健康检查'
for attempt in {1..20}; do
  if curl -fsS "http://127.0.0.1:${HOST_PORT}/health" >/dev/null; then
    break
  fi
  [[ "${attempt}" -lt 20 ]] || { docker logs "${CONTAINER_NAME}"; fail '容器健康检查失败'; }
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

    location / {
        proxy_pass http://127.0.0.1:${HOST_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        add_header Cache-Control "no-store, no-cache, must-revalidate" always;
    }
}
EOF
install -m 0644 "${tmp_conf}" "${NGINX_CONF}"
nginx -t
systemctl reload nginx

log '执行最终检查'
curl -fsS "http://127.0.0.1:${HOST_PORT}/health"
for attempt in {1..10}; do
  if curl -fsS -H "Host: ${SERVER_NAME}" http://127.0.0.1/health; then
    break
  fi
  [[ "${attempt}" -lt 10 ]] || fail '宿主机 Nginx 健康检查失败'
  sleep 1
done
docker ps --filter "name=^/${CONTAINER_NAME}$" --format 'container={{.Names}} status={{.Status}} ports={{.Ports}}'
log "部署成功：http://${SERVER_NAME}/"
