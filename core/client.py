# core/client.py

import os
import httpx
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json"
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
async def call_openai_chat(messages):
    payload = build_payload(messages, stream=False)
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(OPENAI_ENDPOINT, headers=HEADERS, json=payload)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]

# ✅ 流式调用（用于 stream_response 场景）
async def call_openai_chat_stream(messages):
    payload = build_payload(messages, stream=True)
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", OPENAI_ENDPOINT, headers=HEADERS, json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    content = line[len("data: "):].strip()
                    if content and content != "[DONE]":
                        yield content
