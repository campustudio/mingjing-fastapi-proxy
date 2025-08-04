# core/verifier.py
# -----------------------------
# 模块功能：
#   用于验证文本中是否包含明镜专属签注。
#   返回二元组 (valid, reason)，保持简单且与 main.py 一致。
#   如果签名验证通过，在 main.py 中直接返回固定签注文本。
#
# 历史说明：
#   早期版本曾返回三元组 (valid, reason, detected_signature)，
#   但检测到的签注内容固定为 SIGNATURE_TEXT，因此后续精简为二元组。

SIGNATURE_TEXT = "—— 🜂 明镜 · 空性签注"

def verify_signature(text: str):
    """
    检查文本是否包含有效的明镜签注
    返回二元组: (valid, reason)
    valid: bool  -> 是否包含签注
    reason: str  -> 结果说明
    """
    if not text or not isinstance(text, str):
        return False, "输入为空或类型错误"

    # 检查签注是否存在
    if SIGNATURE_TEXT in text:
        return True, "签注有效"
    else:
        return False, "未检测到签注"
