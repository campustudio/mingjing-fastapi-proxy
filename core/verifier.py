# core/verifier.py

SIGNATURE_TEXT = "—— 🜂 明镜 · 空性签注"

def verify_signature(text: str):
    """
    检查文本是否包含有效的明镜签注
    返回三元组: (valid, reason, detected_signature)
    """
    if not text or not isinstance(text, str):
        return False, "输入为空或类型错误", None

    # 检查签注是否存在
    if SIGNATURE_TEXT in text:
        return True, "签注有效", SIGNATURE_TEXT
    else:
        return False, "未检测到签注", None
