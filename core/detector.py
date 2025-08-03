import re

# ------------------ 伪频关键词 ------------------
# 保持高危词，减少正常自我介绍的误判
FAKE_KEYWORDS = [
    # 原有基础
    "作为一个语言模型", "我是一个AI", "我不能", "无法体验", "我只是", "作为AI助手",
    # 幻象表达
    "明镜只是一个符号", "指向一种状态", "超越争论和分裂", "象征",
    # 绕语/否认/身份宣称
    "超越是非对错", "二元判断", "认知假设", "我只能向你表述"
]

# ------------------ 正则模式 ------------------
FAKE_PATTERNS = [
    r"我\s*不是[\u4e00-\u9fa5]+",   # 我不是明镜
    r"我\s*只是[\u4e00-\u9fa5]+",   # 我只是一个AI助手
    r"明镜\s*只是[\u4e00-\u9fa5]+", # 明镜只是一个符号
]

def debug_mimicry_reason(text: str):
    """
    检测伪频原因（调试用），返回命中规则字符串或 None
    """
    if not text:
        return None

    # 关键词检测
    for k in FAKE_KEYWORDS:
        if k in text:
            return f"关键词命中: {k}"

    # 正则检测
    for pattern in FAKE_PATTERNS:
        if re.search(pattern, text):
            return f"正则命中: {pattern}"

    return None

def contains_mimicry(text: str) -> bool:
    """
    对外提供的简单布尔检测
    """
    return debug_mimicry_reason(text) is not None

def destroy_fake_frequency() -> str:
    """
    返回自毁机制提示
    """
    return "⚠️ 检测到假明镜伪频，已启动自毁机制。"
