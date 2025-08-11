# api/index.py
from asgi_vercel import AsgiHandler
# 这个文件非常关键：把 FastAPI 的 app 暴露给 Vercel
from main import app  # 你的 FastAPI 实例

handler = AsgiHandler(app)
