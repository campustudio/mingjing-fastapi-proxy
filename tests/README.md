# Tests (fixed conftest)

## Install
```
pip install -r requirements.txt
pip install pytest pytest-asyncio httpx motor
```

## Run (from project root)
```
pytest -vv tests
# 或者
PYTHONPATH=. pytest -vv tests
```

> 这个测试包自带 `conftest.py` 的路径修复逻辑：
> - 自动把“项目根目录”加入 `sys.path`
> - 如果仍然无法 `import main`，会从文件路径直接加载 `main.py`

覆盖场景：
- `/auth/quick_login` 自动注册/登录
- 单用户消息入库 + 模型入参的上下文拼接
- 上下文长度限制（`CONTEXT_MAX_TURNS`）
- 多用户隔离
