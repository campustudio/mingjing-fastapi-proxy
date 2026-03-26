from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime, timezone
from core.db_mongo import connect, db
from core.auth_utils import create_jwt
from core.wechat_oauth import wx_oauth_login, WxOAuthError
import os
import hashlib

router = APIRouter(prefix="/auth", tags=["auth"])
PURE_AUTH = os.getenv("PURE_AUTH", "false").lower() in ("1","true","yes","y")

class QuickLoginIn(BaseModel):
    username: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str

@router.post("/quick_login", response_model=TokenOut)
async def quick_login(payload: QuickLoginIn):
    username = (payload.username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="username required")

    # 纯净认证模式：不依赖数据库，直接签发临时用户令牌
    if PURE_AUTH:
        # 生成 ASCII-safe 的稳定 uid（避免把中文/Emoji 放入 header/localStorage）
        uid_hash = hashlib.sha256(username.encode("utf-8")).hexdigest()[:16]
        user_id = f"u:{uid_hash}"
        token = create_jwt(user_id, username)
        return TokenOut(access_token=token, user_id=user_id, username=username)
    await connect()
    database = db()
    if database is None:
        raise HTTPException(status_code=500, detail="MongoDB not connected")
    users = database["users"]
    username_lower = username.lower()
    existing = await users.find_one({"username_lower": username_lower})
    now = datetime.now(timezone.utc)
    if existing:
        await users.update_one({"_id": existing["_id"]}, {"$set": {"last_login_at": now}})
        user_id = str(existing["_id"])
    else:
        res = await users.insert_one({
            "username": username,
            "username_lower": username_lower,
            "created_at": now,
            "last_login_at": now,
            "auth_method": "quick",
        })
        user_id = str(res.inserted_id)
    token = create_jwt(user_id, username)
    return TokenOut(access_token=token, user_id=user_id, username=username)


# ─── 微信登录响应模型 ───────────────────────────────────────

class WxLoginOut(BaseModel):
    """微信登录响应"""
    token: str
    user: dict


# ─── 微信登录接口 ───────────────────────────────────────────

@router.get("/wx/login")
async def wechat_login(code: str = Query(..., description="微信授权回调的 code")):
    """
    微信公众号网页授权登录
    
    流程：
    1. 前端跳转微信授权页面获取 code
    2. 前端带 code 调用此接口
    3. 后端用 code 换取 access_token 和用户信息
    4. 后端创建/更新用户记录，返回 JWT
    """
    try:
        token_result, wx_user = await wx_oauth_login(code)
    except WxOAuthError as e:
        raise HTTPException(status_code=400, detail=f"微信登录失败: {e.errmsg}")
    
    await connect()
    database = db()
    if database is None:
        raise HTTPException(status_code=500, detail="MongoDB not connected")
    
    users = database["users"]
    now = datetime.now(timezone.utc)
    
    # 查找或创建用户
    existing = await users.find_one({"wx_openid": wx_user.openid})
    
    if existing:
        # 更新用户信息
        await users.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "wx_nickname": wx_user.nickname,
                "wx_avatar_url": wx_user.headimgurl,
                "wx_last_auth_at": now,
                "last_login_at": now,
            }}
        )
        user_id = str(existing["_id"])
        days = (now - existing.get("created_at", now)).days + 1
    else:
        # 创建新用户
        res = await users.insert_one({
            "username": wx_user.nickname,
            "username_lower": wx_user.nickname.lower(),
            "wx_openid": wx_user.openid,
            "wx_unionid": wx_user.unionid,
            "wx_nickname": wx_user.nickname,
            "wx_avatar_url": wx_user.headimgurl,
            "wx_auth_at": now,
            "wx_last_auth_at": now,
            "created_at": now,
            "last_login_at": now,
            "auth_method": "wechat",
        })
        user_id = str(res.inserted_id)
        days = 1
    
    # 生成 JWT
    token = create_jwt(user_id, wx_user.nickname)
    
    return WxLoginOut(
        token=token,
        user={
            "openid": wx_user.openid,
            "nickname": wx_user.nickname,
            "avatar": wx_user.headimgurl,
            "days": days,
        }
    )
