# api/index.py
from main import app as _app  # main.py 里已有 FastAPI() 的实例 app
app = _app                    # Vercel Python Runtime 会按 ASGI 调用这个 app
