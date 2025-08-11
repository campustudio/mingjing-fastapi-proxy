from typing import Tuple
from httpx import AsyncClient

async def quick_login(client: AsyncClient, username: str) -> tuple[str, str]:
    resp = await client.post("/auth/quick_login", json={"username": username})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return data["access_token"], data["user_id"]
