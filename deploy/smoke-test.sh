#!/usr/bin/env bash
set -Eeuo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1}"
DEPLOY_DIR="${DEPLOY_DIR:-/opt/test-api}"
cd "${DEPLOY_DIR}"
set -a
source .env
set +a
AUTH_HEADER="Authorization: Bearer ${API_TOKEN}"
SAMPLE_FILE="/tmp/test-api-smoke.docx"

docker compose exec -T api python - <<'PY'
from docx import Document
d = Document()
d.add_heading("部署测试报告", 1)
d.add_paragraph("本文件用于验证异步上传、解析、模型总结和查询接口。")
d.save("/tmp/test-api-smoke.docx")
PY
docker cp test-api:/tmp/test-api-smoke.docx "${SAMPLE_FILE}"
trap 'rm -f "${SAMPLE_FILE}"' EXIT

upload_json="$(curl -fsS -H "${AUTH_HEADER}" -F "files=@${SAMPLE_FILE}" "${BASE_URL}/api/v1/documents")"
record_id="$(printf '%s' "${upload_json}" | docker compose exec -T api python -c 'import json,sys; print(json.load(sys.stdin)["records"][0]["id"])')"
batch_id="$(printf '%s' "${upload_json}" | docker compose exec -T api python -c 'import json,sys; print(json.load(sys.stdin)["batch_id"])')"

for attempt in {1..60}; do
  result="$(curl -fsS -H "${AUTH_HEADER}" "${BASE_URL}/api/v1/documents/${record_id}")"
  state="$(printf '%s' "${result}" | docker compose exec -T api python -c 'import json,sys; print(json.load(sys.stdin)["status"])')"
  [[ "${state}" == "SUCCESS" ]] && break
  [[ "${state}" == "FAILED" ]] && { printf '%s\n' "${result}"; exit 1; }
  [[ "${attempt}" -lt 60 ]] || { printf 'timeout: %s\n' "${result}"; exit 1; }
  sleep 2
done

curl -fsS -H "${AUTH_HEADER}" "${BASE_URL}/api/v1/batches/${batch_id}"
curl -fsS -H "${AUTH_HEADER}" "${BASE_URL}/api/v1/documents?page=1&page_size=10"
printf '\nSmoke test passed: record=%s batch=%s\n' "${record_id}" "${batch_id}"
