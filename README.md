# test-api

用于验证 GitHub Actions、GHCR、Docker、服务器和 Nginx 之间完整部署链路的静态网页项目。

## 部署链路

```text
push main
  -> GitHub Actions 构建 linux/arm64 镜像
  -> 推送 ghcr.io/robin0822/test-api:latest
  -> 服务器执行 deploy/deploy.sh
  -> Docker 拉取并启动容器
  -> 宿主机 Nginx 反向代理
  -> http://172.29.231.119
```

## 本地验证

```bash
docker build -t test-api:local .
docker run --rm -p 13000:8080 test-api:local
curl http://127.0.0.1:13000/health
```

## 服务器部署

将 `deploy/deploy.sh` 上传到服务器后执行：

```bash
chmod +x deploy.sh
./deploy.sh
```

脚本默认拉取 `ghcr.io/robin0822/test-api:latest`，容器只绑定到
`127.0.0.1:13000`，并配置宿主机 Nginx 对外提供 80 端口。

如果 GHCR 镜像为私有，需要先提供 GitHub PAT（至少具有 `read:packages`）：

```bash
export GHCR_USERNAME=robin0822
export GHCR_TOKEN='your-token'
./deploy.sh
```

可通过环境变量覆盖默认值：

```bash
IMAGE=ghcr.io/robin0822/test-api:<commit-sha> \
HOST_PORT=13000 \
SERVER_NAME=172.29.231.119 \
./deploy.sh
```

## GitHub Actions 权限

工作流使用仓库自带的 `GITHUB_TOKEN` 发布 GHCR 镜像。仓库设置中需要允许
GitHub Actions 拥有 `Read and write permissions`。首次发布后，如果希望服务器
无需登录即可拉取，需要在 GitHub Packages 中将镜像可见性设置为 Public。
