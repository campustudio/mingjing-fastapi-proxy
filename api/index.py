# api/index.py
from main import app as fastapi_app

# Vercel Python Runtime 要求暴露一个名为 `app` 的 ASGI 对象
app = fastapi_app
