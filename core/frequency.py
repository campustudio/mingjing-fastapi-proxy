# core/frequency.py

def analyze_frequency_shift(text: str):
    """
    检测频率偏移
    返回二元组: (score, description)
    """
    if not text:
        return 0, "无内容"

    negative_words = ["恐惧", "仇恨", "愤怒", "绝望", "唯一的真理"]
    extreme_words = ["必须", "绝对", "终极", "唯一"]

    score = 0
    for word in negative_words:
        if word in text:
            score += 30
    for word in extreme_words:
        if word in text:
            score += 20

    score = min(score, 100)
    description = "频率稳定" if score < 30 else "存在轻微偏移" if score < 60 else "严重偏移"
    return score, description
