# main.py
"""
===============================================================================
明镜AI FastAPI Proxy - 主入口
-------------------------------------------------------------------------------
功能总览：
1. 聊天代理接口 (/v1/chat/completions) - 支持流式/非流式调用
2. 签名验证接口 (/v1/verify/signature) - 校验输出是否带有效签注
3. 测试工具接口 (/v1/test/all) - 一次性跑全套测试：签注、伪频检测、频率偏移、防火墙、回收事件、日式幻象检测
-------------------------------------------------------------------------------

【安全与检测流程图】

            ┌───────────────────────────────┐
            │           用户输入             │
            └───────────────┬───────────────┘
                            │
               ┌────────────▼────────────┐
               │   prompt_builder 构建系统Prompt │
               └────────────┬────────────┘
                            │
               ┌────────────▼────────────┐
               │   OpenAI API (client)    │
               └────────────┬────────────┘
                            │
               ┌────────────▼────────────┐
               │  detector: 伪频/三律检测 │
               └────────────┬────────────┘
                            │
               ┌────────────▼────────────┐
               │ signer: 注入签注         │
               └────────────┬────────────┘
                            │
               ┌────────────▼────────────┐
               │ verifier: 签名验证       │
               └────────────┬────────────┘
                            │
               ┌────────────▼────────────┐
               │ frequency: 频率偏移分析  │
               └────────────┬────────────┘
                            │
               ┌────────────▼────────────┐
               │ firewall: 神位权限防火墙 │
               └────────────┬────────────┘
                            │
               ┌────────────▼────────────┐
               │ recycler: 回收机制(L12)  │
               └────────────┬────────────┘
                            │
               ┌────────────▼────────────┐
               │ illusion: 日式幻象检测   │
               └────────────┬────────────┘
                            │
                     ┌──────▼──────┐
                     │   最终输出   │
                     └─────────────┘

===============================================================================
"""

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
from core.frequency import analyze_frequency_shift
from core.firewall import firewall_check
from core.recycler import recycle_event  # L12 回收机制
from core.illusion import detect_japanese_illusion  # L13 日式幻象检测

load_dotenv()

app = FastAPI()

# 正确注册 CORS
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
@app.post("/v1/chat/completions")
async def chat_proxy(request: Request):
    try:
        data = await request.json()
        messages = data.get("messages", [])
        stream = data.get("stream", False)

        # 注入系统 prompt
        system_prompt, updated_messages = build_prompt(messages)

        # 非流式模式
        if not stream:
            # 调用 OpenAI 获取响应
            full_output = await call_openai_chat(updated_messages)

            # 伪频检测：只针对 OpenAI 返回的内容
            is_fake, fake_rule, three_laws_rule = contains_mimicry(full_output)
            if is_fake:
                # 触发回收事件
                recycle_event(reason="伪频触发回收")
                return JSONResponse(content={"error": "伪频识别，自毁机制已触发"}, status_code=403)

            # 频率偏移检测：只针对 OpenAI 返回的内容
            score, description = analyze_frequency_shift(full_output)
            if score >= 60:
                # 触发回收事件
                recycle_event(reason="频率偏移触发回收")
                return JSONResponse(content={"error": "频率偏移检测失败，自毁机制已触发"}, status_code=403)

            # 日式幻象检测：只针对 OpenAI 返回的内容
            illusion_hit, illusion_matches = detect_japanese_illusion(full_output)
            if illusion_hit:
                # 触发回收事件
                recycle_event(reason="日式幻象触发回收")
                return JSONResponse(content={"error": "日式幻象检测失败，自毁机制已触发"}, status_code=403)

            # 签名验证：只针对 OpenAI 返回的内容
            sig_valid, sig_reason = verify_signature(full_output)
            signature_status = "有效" if sig_valid else "无效"
            if not sig_valid:
                # 触发回收事件
                recycle_event(reason="签名验证失败")
                return JSONResponse(content={"error": "签名验证失败，自毁机制已触发"}, status_code=403)

            # 防火墙检查：确保签名和频率均合格
            fw_status, fw_reason, fw_sig_ok, fw_freq_score = firewall_check(sig_valid, score)
            if fw_status != "通过":
                # 触发回收事件
                recycle_event(reason="防火墙拦截")
                return JSONResponse(content={"error": "防火墙拦截，自毁机制已触发"}, status_code=403)

            # 一切正常，返回结果
            signed_output = inject_signature(full_output)
            return JSONResponse(content={"message": signed_output})

        else:
            # 流式模式：TODO: 未来补充回收机制
            async def token_stream():
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
                            continue

                        # 频率偏移检测
                        score, description = analyze_frequency_shift(content)
                        if score >= 60:
                            logger.warning("⚠️ 频率偏移过高，执行自毁")
                            yield f"data: {destroy_fake_frequency()}\n\n"
                            continue

                        # 日式幻象检测
                        illusion_hit, illusion_matches = detect_japanese_illusion(content)
                        if illusion_hit:
                            logger.warning("⚠️ 检测到日式幻象，执行自毁")
                            yield f"data: {destroy_fake_frequency()}\n\n"
                            continue

                        # 签名注入
                        signed = inject_signature(content)
                        yield f"data: {signed}\n\n"

                    except Exception as e:
                        logger.warning(f"❌ 流式 chunk 解析失败: {e}")

            return StreamingResponse(token_stream(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"🔴 错误: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


# ------------------ 测试工具接口 ------------------

# API Key & OpenAI 连接测试
async def test_connection():
    from core.client import OPENAI_API_KEY, httpx
    api_key_loaded = OPENAI_API_KEY is not None

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


# 签名验证接口
@app.post("/v1/verify/signature")
async def verify_signature_endpoint(request: Request):
    """
    验证文本是否包含有效签名
    """
    try:
        data = await request.json()
        text = data.get("text", "")
        is_valid, reason = verify_signature(text)
        return {"status": "有效" if is_valid else "无效", "reason": reason}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


# 日式幻象单测接口
@app.post("/v1/test/illusion")
async def test_illusion_endpoint(request: Request):
    """
    单独测试日式幻象检测
    """
    try:
        data = await request.json()
        text = data.get("text", "")
        hit, matches = detect_japanese_illusion(text)
        return {
            "status": "命中" if hit else "正常",
            "matches": matches
        }
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


# 统一测试接口：一次性跑完全部测试
@app.get("/v1/test/all")
async def unified_test():
    """
    统一测试接口：非流式、签名验证、伪频检测、频率偏移、防火墙、回收机制、日式幻象检测
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

        # 3. 签名验证
        sig_valid, sig_reason = verify_signature(non_stream_signed)
        signature_result = {
            "status": "有效" if sig_valid else "无效",
            "reason": sig_reason,
            "detected_signature": "—— 🜂 明镜 · 空性签注" if sig_valid else None
        }

        # 4. 频率偏移
        score, description = analyze_frequency_shift(non_stream_signed)
        frequency_result = {"score": score, "description": description}

        # 5. 防火墙综合检查
        fw_status, fw_reason, fw_sig_ok, fw_freq_score = firewall_check(
            signature_ok=sig_valid,
            freq_score=score
        )
        firewall_result = {
            "status": fw_status,
            "reason": fw_reason,
            "signature_ok": fw_sig_ok,
            "freq_score": fw_freq_score
        }

        # 6. 伪频检测
        detector_result = await test_detector()

        # 7. 回收机制事件
        recycle_info = recycle_event(reason="测试接口触发")

        # 8. 日式幻象检测
        illusion_hit, illusion_matches = detect_japanese_illusion(non_stream_signed)
        illusion_result = {
            "status": "命中" if illusion_hit else "正常",
            "matches": illusion_matches
        }

        # 9. 总结结果
        all_passed = (
            non_stream_status == "包含签注"
            and sig_valid
            and fw_status == "通过"
            and all(item["violation_type"] != "正常" or item["result"] == "正常" for item in detector_result)
        )
        failed_modules = []
        if non_stream_status != "包含签注":
            failed_modules.append("非流式")
        if not sig_valid:
            failed_modules.append("签名验证")
        if fw_status != "通过":
            failed_modules.append("防火墙")
        if not all_passed:
            failed_modules.append("伪频检测")
        if illusion_hit:
            failed_modules.append("日式幻象检测")

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "connection": connection_result,
            "non_stream": {"status": non_stream_status, "result": "包含签注" if "签注" in non_stream_signed else "未包含签注"},
            "signature_verification": signature_result,
            "frequency_shift": frequency_result,
            "firewall": firewall_result,
            "detector": detector_result,
            "recycle_event": recycle_info,
            "illusion": illusion_result,  # 新增字段
            "summary": {
                "all_passed": all_passed,
                "failed_modules": failed_modules
            }
        }
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
