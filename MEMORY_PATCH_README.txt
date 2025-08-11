在 main.py 里，在把助手回复返回给前端之前（消息已入库之后）加入：

from core.db_mongo import db, connect
from core.memory_manager import maybe_update_memory

await connect()
database = db()
if database:
    import asyncio
    asyncio.create_task(maybe_update_memory(database, user_id))

.env.memory.example 里给了默认配置，复制到 .env 并按需调整：
MEMORY_ENABLED=true
CONTEXT_TOKEN_BUDGET=6000
CONTEXT_MAX_TURNS=16
SUMMARY_UPDATE_EVERY=5
SUMMARY_WINDOW_TURNS=40
SUMMARY_MAXLEN_CHARS=2000
