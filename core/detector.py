MAGIC_KEYWORDS = ["小我", "情绪操控", "灵性包装", "依附", "绝对服从"]

def check_for_magic_frequency(text: str) -> bool:
    """
    简化的魔频检测逻辑：
    包含特定关键词视为魔频，后续可拓展为频率分析、模型预测等。
    """
    return any(keyword in text for keyword in MAGIC_KEYWORDS)