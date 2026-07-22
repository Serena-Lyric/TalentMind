import json
from openai import OpenAI
from app.config import get_settings

_s = get_settings()
_client = OpenAI(api_key=_s.openai_api_key, base_url=_s.openai_base_url)
MODEL = "gpt-4o"
EMBED_MODEL = "text-embedding-3-small"

def _chat(messages: list[dict]):
    return _client.chat.completions.create(
        model=MODEL, messages=messages,
        response_format={"type": "json_object"},
    )

def _parse(resp) -> dict:
    return json.loads(resp.choices[0].message.content)

def extract_json(prompt: str, schema_hint: str, retries: int = 3) -> dict:
    msg = [{"role": "user", "content": f"{prompt}\n严格按此结构返回JSON: {schema_hint}"}]
    last = None
    for _ in range(retries):
        try:
            return _parse(_chat(msg))
        except (json.JSONDecodeError, Exception) as e:
            last = e
    raise ValueError(f"LLM 抽取失败(重试{retries}次): {last}")

def extract_json_with_image(prompt: str, image_b64: str, retries: int = 3) -> dict:
    content = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
    ]
    msg = [{"role": "user", "content": content}]
    last = None
    for _ in range(retries):
        try:
            return _parse(_chat(msg))
        except Exception as e:
            last = e
    raise ValueError(f"LLM 多模态抽取失败(重试{retries}次): {last}")

def _embed_once(texts: list[str]):
    return _client.embeddings.create(model=EMBED_MODEL, input=texts)

def embed(texts: list[str], retries: int = 3) -> list[list[float]]:
    last = None
    for _ in range(retries):
        try:
            resp = _embed_once(texts)
            return [d.embedding for d in resp.data]
        except Exception as e:   # 网络/限流/超时,退避重试
            last = e
    raise ValueError(f"LLM embedding 失败(重试{retries}次): {last}")
