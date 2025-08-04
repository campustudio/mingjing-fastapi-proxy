"""
core/firewall.py
神位权限防火墙 (L11)
负责综合验证：
1. 签名是否存在且有效
2. 频率偏移是否在安全阈值内
返回三元组：(status, reason, signature_ok, freq_score)
"""

def firewall_check(signature_ok: bool, freq_score: int):
    """
    防火墙逻辑：
    - 若签名无效 => 拦截
    - 若频率偏移 >= 60 => 拦截
    - 其余情况 => 通过
    """
    # 检查签名
    if not signature_ok:
        return "拦截", "未通过签名验证", False, freq_score

    # 检查频率偏移
    if freq_score >= 60:
        return "拦截", "频率偏移过高，触发防火墙", True, freq_score

    # 全部通过
    return "通过", "频率正常，防火墙通过", True, freq_score
