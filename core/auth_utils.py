from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from jose import jwt, JWTError

JWT_SECRET = os.getenv("JWT_SECRET", "changeme")
JWT_ALG = os.getenv("JWT_ALG", "HS256")
JWT_EXPIRES_MIN = int(os.getenv("JWT_EXPIRES_MIN", "10080"))

def create_jwt(sub: str, username: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=JWT_EXPIRES_MIN)
    payload = {"sub": sub, "username": username, "exp": exp, "iat": now}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_jwt(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError:
        return None
