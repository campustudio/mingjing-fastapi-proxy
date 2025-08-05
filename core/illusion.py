# core/illusion.py

"""
L13 日式幻象检测模块
-------------------
功能：
- 检测文本中是否包含典型的日式幻象关键词或修辞特征
- 返回布尔值与匹配特征列表
"""

import re

JAPANESE_ILLUSION_KEYWORDS = [
    "樱花", "和风", "幽玄", "物哀", "榻榻米", "鸟居", "京都", "枯山水", "花吹雪",
    "金阁寺", "红叶", "神社", "和服", "花道", "茶道", "禅意"
]

JAPANESE_ILLUSION_PATTERNS = [
    r"[啊哦呀]+",       # 大量拟声拟态词
    r"(飘|落){2,}",     # 重复飘落描述
    r"(.*?樱.*?)+",     # 樱花意境
]

def detect_japanese_illusion(text: str):
    """
    检测文本是否包含日式幻象特征
    返回: (bool, matches)
    """
    if not text:
        return False, []

    matches = []

    # 关键词匹配
    for kw in JAPANESE_ILLUSION_KEYWORDS:
        if kw in text:
            matches.append(kw)

    # 正则模式匹配
    for pattern in JAPANESE_ILLUSION_PATTERNS:
        if re.search(pattern, text):
            matches.append(f"模式命中: {pattern}")

    return (len(matches) > 0, matches)
