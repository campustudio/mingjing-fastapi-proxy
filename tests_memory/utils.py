from httpx import AsyncClient

async def quick_login(client: AsyncClient, username: str):
    r = await client.post("/auth/quick_login", json={"username": username})
    assert r.status_code == 200, r.text
    data = r.json()
    return data["access_token"], data["user_id"]
