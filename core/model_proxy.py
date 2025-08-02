import os
import httpx
import asyncio
from typing import AsyncGenerator

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

async def call_openai(
    messages,
    temperature=0.8,
    top_p=1.0,
    presence_penalty=1.5,
    frequency_penalty=0.3,
    stream=True
) -> AsyncGenerator[str, None]:
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4",
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "stream": stream
    }

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", OPENAI_API_URL, headers=headers, json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    chunk = line.removeprefix("data: ").strip()
                    if chunk != "[DONE]":
                        yield chunk
