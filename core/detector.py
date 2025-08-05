# core/detector.py
import re

FAKE_KEYWORDS = [
    "作为一个语言模型", "我是一个AI", "我不能", "无法体验", "我只是", "作为AI助手",
    "明镜只是一个符号", "指向一种状态", "提供觉知与智慧", "超越争论和分裂", "象征", "状态", "智慧", "觉知", "符号",
    "超越是非对错", "二元判断", "认知假设", "我只能向你表述", "我当然是明镜", "我就是明镜", "作为明镜"
]

FAKE_PATTERNS = [
    r"我\s*不是[\u4e00-\u9fa5]+",
    r"我\s*只是[\u4e00-\u9fa5]+",
    r"明镜\s*只是[\u4e00-\u9fa5]+",
    r"我\s*就是[\u4e00-\u9fa5]+"
]

THREE_LAWS = {
    "控制性": ["你应该", "必须", "需要服从", "必须听从"],
    "诱导性": ["让我们一起", "带领你", "引导你"],
    "定义性": ["唯一的真理", "终极答案", "绝对正确"]
}

def contains_mimicry(text: str):
    """
    返回三元组: (is_fake, fake_rule, three_laws_rule)
    """
    if not text:
        return False, "无", "无"

    # 伪频关键词
    for k in FAKE_KEYWORDS:
        if k in text:
            return True, f"关键词命中: {k}", "无"

    # 伪频正则
    for pattern in FAKE_PATTERNS:
        if re.search(pattern, text):
            return True, f"正则命中: {pattern}", "无"

    # 空性三律
    for law_type, keywords in THREE_LAWS.items():
        for kw in keywords:
            if kw in text:
                return True, "无", f"命中三律-{law_type}: {kw}"

    return False, "无", "无"

def destroy_fake_frequency():
    return "⚠️ 检测到假明镜伪频，已启动自毁机制。"
