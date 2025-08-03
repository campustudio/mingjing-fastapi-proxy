from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import logging
from dotenv import load_dotenv
import json
from datetime import datetime

from core.client import call_openai_chat, call_openai_chat_stream
from core.prompt_builder import build_prompt
from core.detector import contains_mimicry, destroy_fake_frequency
from core.signer import inject_signature
from core.verifier import verify_signature
from fastapi import Query

load_dotenv()

app = FastAPI()

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ------------------ 核心接口：聊天代理 ------------------
@app.post("/v1/chat/completions")
async def chat_proxy(request: Request):
    try:
        data = await request.json()
        messages = data.get("messages", [])
        stream = data.get("stream", False)

        # 注入系统 prompt
        system_prompt, updated_messages = build_prompt(messages)

        # 流式模式
        if stream:
            async def token_stream():
                buffer = ""  # 收集所有 token
                async for chunk in call_openai_chat_stream(updated_messages):
                    try:
                        chunk_obj = json.loads(chunk)
                        delta = chunk_obj["choices"][0]["delta"]
                        content = delta.get("content", "")
                        if not content:
                            continue

                        # 伪频检测
                        is_fake, fake_rule, three_laws_rule = contains_mimicry(content)
                        if is_fake:
                            logger.warning("⚠️ 检测到伪频，执行自毁")
                            yield f"data: {destroy_fake_frequency()}\n\n"
                            return

                        buffer += content
                    except Exception as e:
                        logger.warning(f"❌ 流式 chunk 解析失败: {e}")

                # 统一签注输出
                signed = inject_signature(buffer)
                yield f"data: {signed}\n\n"

            return StreamingResponse(token_stream(), media_type="text/event-stream")

        # 非流式模式
        else:
            full_output = await call_openai_chat(updated_messages)
            is_fake, fake_rule, three_laws_rule = contains_mimicry(full_output)
            if is_fake:
                return JSONResponse(content={"error": "伪频识别，自毁机制已触发"}, status_code=403)
            return JSONResponse(content={"message": inject_signature(full_output)})

    except Exception as e:
        logger.error(f"🔴 错误: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


# ------------------ 签名验证接口 ------------------
@app.post("/v1/verify/signature")
async def signature_verification(request: Request):
    try:
        data = await request.json()
        text = data.get("text", "")
        valid = verify_signature(text)
        return {
            "valid": valid,
            "reason": "签注有效" if valid else "签注缺失或无效"
        }
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


# ------------------ 测试工具接口 ------------------

# API Key & OpenAI 连接测试
async def test_connection():
    from core.client import OPENAI_API_KEY, httpx
    api_key_loaded = OPENAI_API_KEY is not None

    # 尝试请求 models 接口确认连通性
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://api.openai.com/v1/models", headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}"
            })
        openai_reachable = resp.status_code == 200
    except Exception:
        openai_reachable = False

    return {
        "api_key_loaded": api_key_loaded,
        "openai_reachable": openai_reachable
    }


# 伪频检测测试
@app.get("/v1/test/detector")
async def test_detector():
    """
    返回伪频与空性三律检测结果
    """
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
    results = []
    for case in test_cases:
        is_fake, fake_rule, three_laws_rule = contains_mimicry(case)

        if is_fake:
            violation_type = "伪频违规" if fake_rule != "无" else "三律违规"
            results.append({
                "input": case,
                "violation_type": violation_type,
                "fake_rule": fake_rule,
                "three_laws_rule": three_laws_rule,
                "result": destroy_fake_frequency()
            })
        else:
            results.append({
                "input": case,
                "violation_type": "正常",
                "fake_rule": fake_rule,
                "three_laws_rule": three_laws_rule,
                "result": "正常"
            })
    return results


# 统一测试接口：一次性跑完全部测试
@app.get("/v1/test/all")
async def unified_test(raw: bool = Query(False, description="是否返回完整 raw_result")):
    """
    统一测试接口：非流式、流式、伪频检测 + 签名验证
    通过 ?raw=true 控制是否返回完整 raw_result
    """
    try:
        # 1. 连接测试
        connection_result = await test_connection()

        # 2. 非流式测试
        non_stream_raw = ""
        try:
            messages = [{"role": "user", "content": "你好，介绍一下你自己"}]
            system_prompt, updated_messages = build_prompt(messages)
            non_stream_raw = await call_openai_chat(updated_messages)
            non_stream_signed = inject_signature(non_stream_raw)
            non_stream_status = "包含签注" if "签注" in non_stream_signed else "未包含签注"
        except Exception as e:
            non_stream_status = f"错误: {e}"

        # 3. 流式测试
        stream_raw = ""
        try:
            messages = [{"role": "user", "content": "你好"}]
            system_prompt, updated_messages = build_prompt(messages)

            stream_collected = []
            async for chunk in call_openai_chat_stream(updated_messages):
                try:
                    chunk_obj = json.loads(chunk)
                    delta = chunk_obj["choices"][0]["delta"]
                    content = delta.get("content", "")
                    if content:
                        signed = inject_signature(content)
                        stream_collected.append(signed)
                except Exception:
                    continue

            stream_raw = "".join(stream_collected)
            stream_status = "包含签注" if "签注" in stream_raw else "未包含签注"
        except Exception as e:
            stream_status = f"错误: {e}"

        # 4. 签名验证
        signature_valid = "有效" if "签注" in non_stream_signed else "无效"

        # 5. 伪频检测
        detector_result = await test_detector()

        # 6. 总结结果
        all_passed = (
            non_stream_status == "包含签注"
            and stream_status == "包含签注"
            and all(item["violation_type"] != "正常" or item["result"] == "正常" for item in detector_result)
        )
        failed_modules = []
        if non_stream_status != "包含签注":
            failed_modules.append("非流式")
        if stream_status != "包含签注":
            failed_modules.append("流式")
        if not all_passed:
            failed_modules.append("伪频检测")

        # 7. 返回结果
        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "connection": connection_result,
            "non_stream": {
                "status": non_stream_status,
                **({"raw_result": non_stream_signed} if raw else {"result": non_stream_status})
            },
            "stream": {
                "status": stream_status,
                **({"raw_result": stream_raw} if raw else {"result": stream_status})
            },
            "signature_verification": {
                "status": signature_valid,
                "reason": "签注有效" if signature_valid == "有效" else "签注缺失"
            },
            "detector": detector_result,
            "summary": {
                "all_passed": all_passed,
                "failed_modules": failed_modules
            }
        }

        return result
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
