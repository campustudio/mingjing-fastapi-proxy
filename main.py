from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()  # This loads environment variables from .env

app = FastAPI()

# 允许跨域（部署后前端才能访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 可限制为你的前端地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 从环境变量读取 OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
UPSTREAM_URL = "https://api.openai.com/v1/chat/completions"

if not OPENAI_API_KEY:
    raise RuntimeError("请设置环境变量 OPENAI_API_KEY")


# ✅ 路由支持 /v1/chat/completions（兼容 OpenAI）
@app.post("/v1/chat/completions")
async def proxy_openai_chat(request: Request):
    try:
        payload = await request.json()

        # 构造请求头
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }

        # 处理流式响应
        if payload.get("stream", False):

            async def stream_generator():
                async with httpx.AsyncClient(timeout=60.0) as client:
                    async with client.stream(
                        "POST", UPSTREAM_URL, headers=headers, json=payload
                    ) as r:
                        async for line in r.aiter_lines():
                            if line.strip():
                                yield f"{line}\n"

            return StreamingResponse(stream_generator(), media_type="text/event-stream")

        # 普通响应
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(UPSTREAM_URL, headers=headers, json=payload)
            return JSONResponse(status_code=res.status_code, content=res.json())

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
