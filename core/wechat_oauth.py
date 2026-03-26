"""
微信公众号 OAuth 工具函数

处理微信网页授权流程：
1. 用 code 换取 access_token 和 openid
2. 用 access_token 获取用户信息
"""

import os
import httpx
from typing import Optional
from pydantic import BaseModel

# 微信 API 配置
WX_APPID = os.getenv("WX_APPID", "")
WX_APPSECRET = os.getenv("WX_APPSECRET", "")

# 微信 API 端点
WX_ACCESS_TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"
WX_USERINFO_URL = "https://api.weixin.qq.com/sns/userinfo"


class WxAccessTokenResult(BaseModel):
    """微信 access_token 响应"""
    access_token: str
    expires_in: int
    refresh_token: str
    openid: str
    scope: str
    unionid: Optional[str] = None


class WxUserInfo(BaseModel):
    """微信用户信息"""
    openid: str
    nickname: str
    sex: int
    province: str
    city: str
    country: str
    headimgurl: str
    privilege: list[str] = []
    unionid: Optional[str] = None


class WxOAuthError(Exception):
    """微信 OAuth 错误"""
    def __init__(self, errcode: int, errmsg: str):
        self.errcode = errcode
        self.errmsg = errmsg
        super().__init__(f"微信 OAuth 错误 [{errcode}]: {errmsg}")


async def get_access_token(code: str) -> WxAccessTokenResult:
    """
    用 code 换取 access_token 和 openid
    
    Args:
        code: 微信授权回调的 code 参数
        
    Returns:
        WxAccessTokenResult: 包含 access_token, openid 等信息
        
    Raises:
        WxOAuthError: 微信 API 返回错误
    """
    params = {
        "appid": WX_APPID,
        "secret": WX_APPSECRET,
        "code": code,
        "grant_type": "authorization_code",
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(WX_ACCESS_TOKEN_URL, params=params)
        data = response.json()
        
    if "errcode" in data:
        raise WxOAuthError(data["errcode"], data.get("errmsg", "未知错误"))
    
    return WxAccessTokenResult(**data)


async def get_user_info(access_token: str, openid: str) -> WxUserInfo:
    """
    获取微信用户信息
    
    Args:
        access_token: 微信 access_token
        openid: 用户 openid
        
    Returns:
        WxUserInfo: 用户信息（昵称、头像等）
        
    Raises:
        WxOAuthError: 微信 API 返回错误
    """
    params = {
        "access_token": access_token,
        "openid": openid,
        "lang": "zh_CN",
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(WX_USERINFO_URL, params=params)
        data = response.json()
        
    if "errcode" in data:
        raise WxOAuthError(data["errcode"], data.get("errmsg", "未知错误"))
    
    return WxUserInfo(**data)


async def wx_oauth_login(code: str) -> tuple[WxAccessTokenResult, WxUserInfo]:
    """
    完整的微信 OAuth 登录流程
    
    Args:
        code: 微信授权回调的 code 参数
        
    Returns:
        tuple: (access_token_result, user_info)
    """
    token_result = await get_access_token(code)
    user_info = await get_user_info(token_result.access_token, token_result.openid)
    return token_result, user_info
