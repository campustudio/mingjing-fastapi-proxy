#!/usr/bin/env python3
"""
检查微信用户同步状态的脚本
"""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

async def check_users():
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        print("❌ MONGODB_URI 环境变量未设置")
        return
    
    client = AsyncIOMotorClient(mongo_uri)
    # 直接使用 mingjing 数据库
    db = client.mingjing
    users = db.users
    
    print("=" * 50)
    print("微信用户同步状态检查")
    print("=" * 50)
    
    # 查找所有微信用户
    wx_users = await users.find({"wx_openid": {"$exists": True}}).to_list(100)
    
    print(f"\n📊 微信用户总数: {len(wx_users)}")
    print("-" * 50)
    
    for i, user in enumerate(wx_users, 1):
        print(f"\n用户 #{i}")
        print(f"  ID: {user.get('_id')}")
        print(f"  昵称: {user.get('wx_nickname', 'N/A')}")
        print(f"  OpenID: {user.get('wx_openid', 'N/A')[:20]}...")
        print(f"  头像: {user.get('wx_avatar_url', 'N/A')[:50]}..." if user.get('wx_avatar_url') else "  头像: N/A")
        print(f"  创建时间: {user.get('created_at', 'N/A')}")
        print(f"  最后登录: {user.get('last_login_at', 'N/A')}")
    
    print("\n" + "=" * 50)
    print("✅ 检查完成")
    print("=" * 50)
    
    client.close()

if __name__ == "__main__":
    asyncio.run(check_users())
