from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
from core.db_mongo import connect, db
from core.auth_utils import create_jwt

router = APIRouter(prefix="/auth", tags=["auth"])

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
