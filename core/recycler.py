"""
core/recycler.py - L12 优雅中止 & 回收机制
-------------------------------------------
功能：
1. 触发回收事件（伪频检测/防火墙拒绝/用户指令）
2. 记录回收原因和时间戳
3. 为 /v1/test/all 提供状态字段
"""

from datetime import datetime

# 全局缓存上一次回收事件（可后续改为持久化）
_last_recycle_event = None


def recycle_event(reason: str):
    """
    触发回收事件，记录时间戳和原因
    返回事件信息字典
    """
    global _last_recycle_event
    _last_recycle_event = {
        "event": "recycle",
        "reason": reason,
        "timestamp": datetime.utcnow().isoformat()
    }
    return _last_recycle_event


def get_last_recycle_event():
    """
    获取最近一次回收事件（若无则返回默认状态）
    """
    if _last_recycle_event:
        return _last_recycle_event
    return {
        "event": "recycle",
        "reason": "无回收事件",
        "timestamp": None
    }
