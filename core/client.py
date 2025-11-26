# core/client.py

import os
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")
OPENAI_ENDPOINT = f"{OPENAI_API_BASE}/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Connection": "close",
    "User-Agent": "MingjingProxy/1.0"
}

# 请求 payload 构造（共用）
def build_payload(messages, stream=True):
    return {
        "model": "gpt-4",
        "messages": messages,
        "stream": stream,
        "temperature": 0.8,
        "top_p": 1.0,
        "presence_penalty": 1.5,
        "frequency_penalty": 0.3,
    }

# ✅ 非流式调用（用于后端直接拿结果时）
async def call_openai_chat(updated_messages):
    """
    合并系统 prompt 和上下文，并调用 OpenAI 获取响应
    """
    # 打印调试信息，确认合并后的 payload
    payload = build_payload(updated_messages, stream=False)
    print("🧠 注入后 payload:", payload)

    # 调用 OpenAI API 获取响应
    timeout = httpx.Timeout(40.0)
    limits = httpx.Limits(max_connections=10, max_keepalive_connections=0, keepalive_expiry=0)
    async with httpx.AsyncClient(timeout=timeout, http2=False, limits=limits, headers=HEADERS, trust_env=False) as client:
        for attempt in range(3):
            try:
                res = await client.post(OPENAI_ENDPOINT, json=payload)
                res.raise_for_status()
                return res.json()["choices"][0]["message"]["content"]
            except (httpx.RemoteProtocolError, httpx.LocalProtocolError, httpx.ReadError, httpx.ConnectError):
                if attempt < 2:
                    await asyncio.sleep(0.2 * (2 ** attempt))
                    continue
                break
            except httpx.HTTPStatusError as e:
                status = e.response.status_code if e.response is not None else None
                if status in (502, 503, 504) and attempt < 2:
                    await asyncio.sleep(0.2 * (2 ** attempt))
                    continue
                raise

    def _sync_call():
        try:
            import requests as _req
        except Exception as _e:
            raise RuntimeError("requests not available for fallback") from _e
        r = _req.post(OPENAI_ENDPOINT, headers=HEADERS, json=payload, timeout=40)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    return await asyncio.to_thread(_sync_call)

# ✅ 流式调用（用于 stream_response 场景）
async def call_openai_chat_stream(updated_messages):
    """
    合并系统 prompt 和上下文，并流式获取 OpenAI 响应
    """
    payload = build_payload(updated_messages, stream=True)
    timeout = httpx.Timeout(None)
    limits = httpx.Limits(max_connections=10, max_keepalive_connections=0, keepalive_expiry=0)
    async with httpx.AsyncClient(timeout=timeout, http2=False, limits=limits, headers=HEADERS, trust_env=False) as client:
        async with client.stream("POST", OPENAI_ENDPOINT, json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    content = line[len("data: "):].strip()
                    if content and content != "[DONE]":
                        yield content

