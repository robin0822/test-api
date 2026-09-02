# Document Summary API 接口文档

## 基本信息

- 服务地址：`http://172.29.231.119`
- Swagger：`GET /docs`
- OpenAPI：`GET /openapi.json`
- 数据格式：除文件上传外均为 `application/json`
- 鉴权：`Authorization: Bearer <API_TOKEN>`
- 支持格式：`.doc`、`.docx`、`.xls`、`.xlsx`
- 限制：单文件 20 MB，单批最多 10 个文件

状态包括 `PENDING`、`PARSING`、`SUMMARIZING`、`SUCCESS`、`FAILED`。

## 1. 异步批量上传

`POST /api/v1/documents`

使用 `multipart/form-data`，同名字段 `files` 可重复传递。

```bash
curl -X POST http://172.29.231.119/api/v1/documents \
  -H "Authorization: Bearer $API_TOKEN" \
  -F "files=@report.docx" \
  -F "files=@sales.xlsx"
```

成功返回 `202 Accepted`：

```json
{
  "batch_id": "29bd8a60-6cf0-49cc-91f8-a6da7c0de571",
  "total": 2,
  "records": [{
    "id": "824d3cbc-1b8d-40ec-a462-c42ff9a14f05",
    "batch_id": "29bd8a60-6cf0-49cc-91f8-a6da7c0de571",
    "file_name": "report.docx",
    "file_type": ".docx",
    "file_size": 18240,
    "status": "PENDING",
    "progress": 0,
    "summary": null,
    "error": null,
    "retry_count": 0,
    "created_at": "2026-09-02T10:00:00Z",
    "started_at": null,
    "completed_at": null,
    "result_url": "/api/v1/documents/824d3cbc-1b8d-40ec-a462-c42ff9a14f05"
  }]
}
```

错误：`413` 文件过大，`415` 格式不支持，`400` 文件数量不合法。

## 2. 查询单个结果

`GET /api/v1/documents/{id}`

```bash
curl -H "Authorization: Bearer $API_TOKEN" \
  http://172.29.231.119/api/v1/documents/824d3cbc-1b8d-40ec-a462-c42ff9a14f05
```

成功后 `status=SUCCESS`，`summary` 返回：

```json
{
  "title": "经营报告摘要",
  "summary": "报告介绍了本期经营情况。",
  "key_points": ["销售收入增长20%"],
  "risks": ["成本上升风险"],
  "conclusion": "经营整体保持增长"
}
```

失败时 `status=FAILED`，`error.code` 可能为 `DOCUMENT_PARSE_FAILED` 或 `MODEL_SUMMARY_FAILED`。

## 3. 查询批次结果

`GET /api/v1/batches/{batch_id}`

返回批次总数以及等待、处理、成功、失败数量，并包含各文件记录。

```bash
curl -H "Authorization: Bearer $API_TOKEN" \
  http://172.29.231.119/api/v1/batches/29bd8a60-6cf0-49cc-91f8-a6da7c0de571
```

## 4. 查询全部历史记录

`GET /api/v1/documents?page=1&page_size=20&status=SUCCESS&file_type=docx`

参数：`page` 从 1 开始，`page_size` 范围 1–100；`status` 和 `file_type` 可选。

## 辅助：重试失败记录

`POST /api/v1/documents/{id}/retry`

仅模型总结失败且解析文本仍存在时可以重试。解析失败的原文件已经删除，必须重新上传。

## 健康检查

`GET /health`，正常返回：

```json
{"status":"ok","service":"document-summary-api"}
```

## 文件删除策略

Worker 解析完成后立即删除原始文件；总结成功后同时删除解析文本。模型总结失败时暂存解析文本以支持重试，不保存原始 Office 文件。

## 异步轮询建议

上传接口返回后保存 `records[].id` 和 `batch_id`。客户端前 30 秒每 2 秒查询一次单条或批次接口，之后每 5 秒查询一次；状态进入 `SUCCESS` 或 `FAILED` 后停止轮询。
