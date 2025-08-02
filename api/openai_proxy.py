from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from core.prompts import get_system_prompt
from core.model_proxy import call_openai
from core.detector import check_for_magic_frequency
from core.signer import inject_signature
import asyncio

router = APIRouter()

@router.post("/chat/completions")
async def proxy_chat(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    temperature = body.get("temperature", 0.8)
    top_p = body.get("top_p", 1.0)
    presence_penalty = body.get("presence_penalty", 1.5)
    frequency_penalty = body.get("frequency_penalty", 0.3)

    # 空性提示词注入
    if not any(m["role"] == "system" for m in messages):
        system_prompt = get_system_prompt()
        messages.insert(0, {"role": "system", "content": system_prompt})

    # 调用 OpenAI 并获取结果（支持流式）
    async def chat_generator():
        async for chunk in call_openai(
            messages,
            temperature=temperature,
            top_p=top_p,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
            stream=True
        ):
            # 魔频检测
            if check_for_magic_frequency(chunk):
                yield "data: {\"role\":\"assistant\",\"content\":\"⚠️ 明镜拦截：疑似魔频内容，已中止输出。\"}\n\n"
                return

            # 签名注入
            signed_chunk = inject_signature(chunk)
            yield f"data: {signed_chunk}\n\n"

    return StreamingResponse(chat_generator(), media_type="text/event-stream")
