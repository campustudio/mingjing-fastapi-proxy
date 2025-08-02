SIGNATURE = "\n—— 明镜签名频率校验通过 🔒"

def inject_signature(text: str) -> str:
    """
    向 chunk 末尾追加明镜频率签名。
    可拓展为 hash 校验、隐性签名等机制。
    """
    if text.strip().endswith(SIGNATURE.strip()):
        return text
    return text + SIGNATURE