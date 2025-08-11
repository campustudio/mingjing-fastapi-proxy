import os, sys, uuid, asyncio, pathlib, importlib.util, importlib
import pytest
import pytest_asyncio
import httpx

TEST_DB = f"mingjing_test_{uuid.uuid4().hex[:8]}"
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGODB_DB", TEST_DB)
os.environ.setdefault("JWT_SECRET", "test-secret-please-change")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("CONTEXT_MAX_TURNS", "16")
os.environ.setdefault("CONTEXT_TOKEN_BUDGET", "6000")
os.environ.setdefault("MEMORY_ENABLED", "true")
os.environ.setdefault("SUMMARY_UPDATE_EVERY", "2")
os.environ.setdefault("SUMMARY_WINDOW_TURNS", "10")

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import main as app_main
except ModuleNotFoundError:
    main_py = ROOT/"main.py"
    spec = importlib.util.spec_from_file_location("app_main", main_py)
    app_main = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(app_main)

app = app_main.app

# ---- Mock OpenAI calls everywhere ----
last_payload = {"messages": None}
async def _mock_call_openai_chat(updated_messages):
    last_payload["messages"] = list(updated_messages)
    return "## Long-term memory summary\n用户偏好：客观表达。\n\n## Facts\n- 喜欢结构化输出\n- 正在构建明镜项目"

async def _mock_stream(updated_messages):
    import json
    for chunk in ["你好", "，世界"]:
        yield json.dumps({"choices":[{"delta":{"content":chunk}}]})

for name in ("main", "core.client", "core.memory_manager"):
    try:
        m = importlib.import_module(name)
    except Exception:
        continue
    if hasattr(m, "call_openai_chat"):
        setattr(m, "call_openai_chat", _mock_call_openai_chat)
    if hasattr(m, "call_openai_chat_stream"):
        setattr(m, "call_openai_chat_stream", _mock_stream)

@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.fixture
def payload_recorder():
    return last_payload

# Reset Motor globals per test
@pytest_asyncio.fixture(autouse=True)
async def fresh_mongo_client():
    import core.db_mongo as dbm
    try:
        if getattr(dbm, "_MONGO_CLIENT", None):
            dbm._MONGO_CLIENT.close()
    except Exception:
        pass
    dbm._MONGO_CLIENT = None
    dbm._DB = None
    yield
    try:
        if getattr(dbm, "_MONGO_CLIENT", None):
            dbm._MONGO_CLIENT.close()
    except Exception:
        pass
    dbm._MONGO_CLIENT = None
    dbm._DB = None
