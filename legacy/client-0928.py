# core/client.py —— 快速非流式（gpt-5-mini 优先，裁剪上下文，限制输出）
import os, json, asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise RuntimeError("OPENAI_API_KEY 未设置")

MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini").strip()
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "256"))   # 调小更快
TURN_CAP = int(os.getenv("TURN_CAP", "6"))                        # 最近 N 轮

CHAT_URL = "https://api.openai.com/v1/chat/completions"
RESP_URL = "https://api.openai.com/v1/responses"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "User-Agent": "mingjing-proxy/fast-0.3",
}

# ---- 连接池（HTTP/1.1 + keepalive），小重试 ----
_timeout = httpx.Timeout(60.0, connect=8.0, read=60.0, write=60.0)
_limits  = httpx.Limits(max_connections=20, max_keepalive_connections=10, keepalive_expiry=20.0)
_CLIENT  = httpx.AsyncClient(timeout=_timeout, limits=_limits, http2=False, trust_env=False)

def _trim_messages(msgs):
    if not isinstance(msgs, list):
        return msgs
    # 保留最后 TURN_CAP 条（你也可以按「role=user/assistant」成对裁剪）
    return msgs[-TURN_CAP:]

def _to_responses_input(messages):
    out = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        blocks = []
        if isinstance(content, str):
            blocks.append({"type": "input_text", "text": content})
        elif isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    blocks.append({"type": "input_text", "text": c.get("text", "")})
                elif isinstance(c, dict) and c.get("type") == "image_url":
                    blocks.append({"type": "input_image", "image_url": c.get("image_url")})
                else:
                    blocks.append({"type": "input_text", "text": str(c)})
        else:
            blocks.append({"type": "input_text", "text": str(content)})
        out.append({"role": role, "content": blocks})
    return out

def _extract_output_text(obj):
    if isinstance(obj.get("output_text"), str):
        return obj["output_text"]
    parts = []
    for item in obj.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") in ("output_text", "text"):
                    t = c.get("text")
                    if t: parts.append(t)
    return "".join(parts)

async def _post_json(url, payload, *, tries=2):
    attempt = 0
    while True:
        try:
            r = await _CLIENT.post(url, headers=HEADERS, json=payload)
            r.raise_for_status()
            return r
        except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadTimeout):
            attempt += 1
            if attempt >= tries:
                raise
            await asyncio.sleep(0.25 * attempt)  # 轻量退避
        except httpx.HTTPStatusError:
            raise

# ---------- 非流式 ----------
async def call_openai_chat(updated_messages):
    msgs = _trim_messages(updated_messages or [])
    if MODEL.startswith("gpt-5"):
        payload = {"model": MODEL, "input": _to_responses_input(msgs)}
        if MAX_OUTPUT_TOKENS > 0:
            payload["max_output_tokens"] = MAX_OUTPUT_TOKENS
        r = await _post_json(RESP_URL, payload, tries=2)
        return _extract_output_text(r.json())
    else:
        payload = {"model": MODEL, "messages": msgs, "stream": False}
        if MAX_OUTPUT_TOKENS > 0:
            payload["max_tokens"] = MAX_OUTPUT_TOKENS
        r = await _post_json(CHAT_URL, payload, tries=2)
        data = r.json()
        return data["choices"][0]["message"]["content"]

# ---------- 流式（保持最简，不动你的前端解析） ----------
async def call_openai_chat_stream(updated_messages):
    # 仍然按非流式一次性返回，保持你 main.py 的 JSON 解析兼容
    text = await call_openai_chat(updated_messages)
    return iter([json.dumps({"choices": [{"delta": {"content": text}}]})])
