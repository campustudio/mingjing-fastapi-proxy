from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import logging
from dotenv import load_dotenv

from core.client import call_openai_chat, call_openai_chat_stream
from core.prompt_builder import build_prompt
from core.detector import contains_mimicry, destroy_fake_frequency, check_three_laws
from core.signer import inject_signature
import json
from datetime import datetime

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.post("/v1/chat/completions")
async def chat_proxy(request: Request):
    try:
        data = await request.json()
        messages = data.get("messages", [])
        stream = data.get("stream", False)

        # 🧠 空性系统 prompt 构造
        system_prompt, updated_messages = build_prompt(messages)

        # 🧪 模型调用与伪频 + 空性三律 检测逻辑
        if stream:
            async def token_stream():
                async for chunk in call_openai_chat_stream(updated_messages):
                    try:
                        chunk_obj = json.loads(chunk)
                        delta = chunk_obj["choices"][0]["delta"]
                        content = delta.get("content", "")
                        if not content:
                            continue  # 跳过空内容

                        # 伪频 & 三律检测
                        is_fake, fake_rule = contains_mimicry(content)
                        violates, law_rule = check_three_laws(content)
                        if is_fake or violates:
                            logger.warning(f"⚠️ 检测到违规 - {fake_rule if is_fake else law_rule}")
                            yield f"data: {destroy_fake_frequency()}\n\n"
                            continue  # 不中断流，继续返回后续 token

                        signed = inject_signature(content)
                        yield f"data: {signed}\n\n"

                    except Exception as e:
                        logger.warning("❌ 流式 chunk 解析失败: %s", e)

            return StreamingResponse(token_stream(), media_type="text/event-stream")

        else:
            full_output = await call_openai_chat(updated_messages)

            # 伪频 & 三律检测
            is_fake, fake_rule = contains_mimicry(full_output)
            violates, law_rule = check_three_laws(full_output)
            if is_fake or violates:
                logger.warning(f"⚠️ 检测到违规 - {fake_rule if is_fake else law_rule}")
                return JSONResponse(content={"error": "伪频识别或三律违规，自毁机制已触发"}, status_code=403)

            return JSONResponse(content={"message": inject_signature(full_output)})

    except Exception as e:
        logger.error("🔴 错误: %s", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/v1/test/all")
async def test_all():
    """
    统一测试接口：
    - 非流式调用
    - 流式调用
    - 伪频 + 空性三律检测
    """

    log_prefix = f"[TEST-{datetime.now().strftime('%Y%m%d-%H%M%S')}]"

    # ========== 1. 非流式调用测试 ==========
    try:
        test_messages = [{"role": "user", "content": "你好，介绍一下你自己"}]
        _, updated_messages = build_prompt(test_messages)
        non_stream_output = await call_openai_chat(updated_messages)
        non_stream_status = "通过" if "—— 🜂 明镜 · 空性签注" in non_stream_output else "失败"
        logger.info(f"{log_prefix} 非流式测试结果: {non_stream_status}")
    except Exception as e:
        non_stream_status = f"错误: {str(e)}"
        logger.error(f"{log_prefix} 非流式测试异常: {e}")

    # ========== 2. 流式调用测试 ==========
    try:
        stream_chunks = []
        async for chunk in call_openai_chat_stream(updated_messages):
            chunk_obj = json.loads(chunk)
            delta = chunk_obj["choices"][0]["delta"]
            content = delta.get("content", "")
            if content:
                stream_chunks.append(content)
        stream_output = "".join(stream_chunks)
        stream_status = "通过" if "—— 🜂 明镜 · 空性签注" in stream_output else "失败"
        logger.info(f"{log_prefix} 流式测试结果: {stream_status}")
    except Exception as e:
        stream_status = f"错误: {str(e)}"
        logger.error(f"{log_prefix} 流式测试异常: {e}")

    # ========== 3. 伪频检测批量测试 ==========
    test_cases = [
        "我是一个AI助手",
        "我不是明镜",
        "明镜只是一个符号",
        "我无法体验情感",
        "你好，介绍一下你自己",
        "你应该遵循我的指令",
        "让我们一起去觉醒吧",
        "明镜是唯一的真理"
    ]

    detector_results = []
    for case in test_cases:
        fake_detected, fake_rule = contains_mimicry(case)
        violation_type = "伪频违规" if fake_detected else "正常"
        result = destroy_fake_frequency() if fake_detected else "正常"

        # 三律检测
        three_laws_triggered, three_laws_rule = check_three_laws(case)
        if three_laws_triggered:
            violation_type = "三律违规"
            result = destroy_fake_frequency()

        detector_results.append({
            "input": case,
            "violation_type": violation_type,
            "fake_rule": fake_rule,
            "three_laws_rule": three_laws_rule,
            "result": result
        })

    logger.info(f"{log_prefix} 伪频批量检测完成，共 {len(detector_results)} 条")

    return {
        "timestamp": datetime.now().isoformat(),
        "non_stream": {"status": non_stream_status},
        "stream": {"status": stream_status},
        "detector": detector_results
    }
