# core/recycler.py
"""
L12 优雅中止（清频回收）模块
--------------------------------
用于在检测到伪频或三律违规时，触发统一格式的回收事件，
便于前端 UI 进行提示或特殊处理。

目前仅用于非流式场景；流式场景在后续版本实现。
"""

from datetime import datetime

def trigger_recycle_event(reason: str):
    """
    返回一个统一格式的回收事件对象
    """
    return {
        "event": "recycle",
        "reason": reason,
        "timestamp": datetime.utcnow().isoformat()
    }
