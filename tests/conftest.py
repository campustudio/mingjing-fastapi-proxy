# tests/conftest.py
import os, sys, uuid, asyncio, pathlib, importlib.util
import pytest
import pytest_asyncio
from httpx import AsyncClient
import httpx
import importlib

# tests/conftest.py 里，其他 import 下面加：
import pytest_asyncio

# 每个测试用独立的 Motor 客户端（避免跨测试复用已绑定旧事件循环的 client）
@pytest_asyncio.fixture(autouse=True)
async def fresh_mongo_client():
    import core.db_mongo as dbm
    # ---- before each test ----
    try:
        if getattr(dbm, "_MONGO_CLIENT", None):
            dbm._MONGO_CLIENT.close()
    except Exception:
        pass
    dbm._MONGO_CLIENT = None
    dbm._DB = None

    yield

    # ---- after each test ----
    try:
        if getattr(dbm, "_MONGO_CLIENT", None):
            dbm._MONGO_CLIENT.close()
    except Exception:
        pass
    dbm._MONGO_CLIENT = None
    dbm._DB = None


# ---------- Env (before importing app) ----------
TEST_DB = f"mingjing_test_{uuid.uuid4().hex[:8]}"
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGODB_DB", TEST_DB)
os.environ.setdefault("JWT_SECRET", "test-secret-please-change")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("CONTEXT_MAX_TURNS", "3")

# ---------- Ensure project root on sys.path ----------
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------- Import FastAPI app (with fallback) ----------
try:
    import main as app_main
except ModuleNotFoundError:
    main_py = ROOT / "main.py"
    if not main_py.exists():
        raise RuntimeError(f"找不到 main.py：{main_py}")
    spec = importlib.util.spec_from_file_location("app_main", main_py)
    app_main = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(app_main)

app = app_main.app  # FastAPI instance

# ---------- Patch OpenAI client to avoid network ----------
from core import client as core_client
last_payload = {"messages": None}

@pytest.fixture(autouse=True)
def patch_llm(monkeypatch):
    async def _mock_call_openai_chat(updated_messages):
        # 记录传给 LLM 的上下文
        last_payload["messages"] = list(updated_messages)
        return "MOCK_REPLY"

    async def _mock_stream(updated_messages):
        import json
        for chunk in ["你好", "，世界"]:
            yield json.dumps({"choices":[{"delta":{"content":chunk}}]})

    # 每个测试用例开始前清零一次
    last_payload["messages"] = None

    # 1) 打补丁到核心模块（main 里委托也会走到这）
    monkeypatch.setattr(core_client, "call_openai_chat", _mock_call_openai_chat, raising=True)
    monkeypatch.setattr(core_client, "call_openai_chat_stream", _mock_stream, raising=True)

    # 2) 也打到 main 的包装函数（确保 globals()["call_openai_chat"] 命中）
    import main as _main
    monkeypatch.setattr(_main, "call_openai_chat", _mock_call_openai_chat, raising=False)
    monkeypatch.setattr(_main, "call_openai_chat_stream", _mock_stream, raising=False)

# ---------- Fixtures (pytest-asyncio strict friendly) ----------
@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture
async def client():
    # 让 FastAPI 在测试里以 ASGI 方式运行（新版 httpx 用 ASGITransport）
    transport = httpx.ASGITransport(app=app)  # ← 去掉 lifespan 参数
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.fixture
def payload_recorder():
    return last_payload
