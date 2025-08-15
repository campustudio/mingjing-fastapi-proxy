# api/index.py
from asgi_vercel import AsgiHandler
from main import app as fastapi_app

handler = AsgiHandler(fastapi_app)
