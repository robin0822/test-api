# Document Summary API

Word/Excel 异步模型总结服务。支持 `.doc`、`.docx`、`.xls`、`.xlsx` 批量上传，通过 FastAPI、Celery、Redis 和 PostgreSQL 完成异步解析与总结。旧版 `.doc/.xls` 分别由 Antiword 和 xlrd 提取。

## 核心接口

- `POST /api/v1/documents`：异步批量上传
- `GET /api/v1/documents/{id}`：查询单个结果
- `GET /api/v1/batches/{batch_id}`：查询批次结果
- `GET /api/v1/documents`：分页查询历史记录
- `POST /api/v1/documents/{id}/retry`：重试模型总结失败记录
- `GET /health`：健康检查

完整说明见 [docs/API.md](docs/API.md)，服务启动后也可访问 `/docs`。

## 本地启动

```bash
cp .env.example .env
# 修改 .env 中的密码、API Token 和 MODEL_API_KEY
docker compose up -d
curl http://127.0.0.1:13000/health
```

基础设施联调时可设置 `MODEL_MOCK=true`；真实模型测试必须设置新生成的 `MODEL_API_KEY`。

## 测试

```bash
pytest -q
```

服务器端完整链路：

```bash
deploy/smoke-test.sh
```

手动构建 ARM64 镜像：

```bash
PUSH=true IMAGE=ghcr.io/robin0822/test-api deploy/build-image.sh
```

## 部署

完成本地 API 验证后，在 GitHub Actions 页面手动触发工作流，构建 `linux/arm64` 镜像并发布：

```text
ghcr.io/robin0822/test-api:latest
```

服务器执行：

```bash
chmod +x deploy/deploy-v2.sh
./deploy/deploy-v2.sh
```

部署目录为 `/opt/test-api`。模型密钥只允许写入服务器的 `/opt/test-api/.env`，禁止提交到 Git。
