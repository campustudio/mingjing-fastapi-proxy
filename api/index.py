from asgi_vercel import AsgiHandler, VercelResponse
from main import app as fastapi_app

# Vercel 入口
handler = AsgiHandler(fastapi_app)

# 可选：/api/index.py 直连测试用
async def index(request):
    return VercelResponse("OK", status_code=200)
