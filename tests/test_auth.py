import pytest
from .utils import quick_login

@pytest.mark.asyncio
async def test_quick_login_creates_user_and_returns_jwt(client):
    token1, user_id1 = await quick_login(client, "alice")
    assert token1 and user_id1

    token2, user_id2 = await quick_login(client, "Alice")  # case-insensitive
    assert user_id2 == user_id1
    assert token2 != ""
