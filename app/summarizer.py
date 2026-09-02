import json
from openai import OpenAI
from app.config import get_settings

SYSTEM_PROMPT = """你是企业文档分析助手。请严格依据输入内容生成中文摘要，不得虚构。
只输出合法 JSON，字段必须包含：title、summary、key_points、risks、conclusion。
key_points 和 risks 必须是字符串数组。"""


def _chunks(text: str, size: int) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)]


def _chat(client: OpenAI, content: str) -> str:
    settings = get_settings()
    response = client.chat.completions.create(
        model=settings.model_id,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}],
        temperature=settings.model_temperature,
        max_tokens=settings.model_max_tokens,
        extra_headers={"lora_id": "0"},
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content or "{}"


def summarize_document(text: str, file_name: str) -> dict:
    settings = get_settings()
    if settings.model_mock:
        return {"title": f"{file_name} 摘要", "summary": f"测试模式已解析文档，共 {len(text)} 个字符。", "key_points": ["文件解析成功", "异步任务执行成功"], "risks": [], "conclusion": "部署链路验证成功。"}
    if not settings.model_api_key:
        raise RuntimeError("MODEL_API_KEY is not configured")
    client = OpenAI(api_key=settings.model_api_key, base_url=settings.model_api_base, timeout=120, max_retries=2)
    chunks = _chunks(text, settings.model_chunk_chars)
    partials = [_chat(client, f"文件名：{file_name}\n这是第 {i}/{len(chunks)} 段，请总结本段：\n\n{chunk}") for i, chunk in enumerate(chunks, 1)]
    result_text = partials[0] if len(partials) == 1 else _chat(client, f"文件名：{file_name}\n请合并以下分段摘要：\n" + "\n".join(partials))
    try:
        result = json.loads(result_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Model returned invalid JSON") from exc
    for key in ("title", "summary", "key_points", "risks", "conclusion"):
        if key not in result:
            raise RuntimeError(f"Model response missing field: {key}")
    return result
