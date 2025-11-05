# 技术债偿还进度

## ✅ 阶段一：紧急止血（已完成）

### 1. 前端错误边界 ✅
**文件**: `mingjing-ai-prototype/src/components/ErrorBoundary.jsx`

**改动**:
- 创建 React ErrorBoundary 组件，捕获子组件崩溃
- 在 `main.jsx` 中包裹 App 组件
- 开发模式下显示错误堆栈，生产模式下显示友好提示
- 提供"刷新页面"和"继续尝试"两个恢复选项

**验证方法**:
```javascript
// 在任意组件中手动抛出错误测试
throw new Error('测试错误边界');
```

**收益**: 
- 防止整个应用白屏
- 提升用户体验，不会因为局部错误导致完全不可用

---

### 2. 请求重试机制 ✅
**文件**: `mingjing-ai-prototype/src/utils/aiClients.js`

**改动**:
- 新增 `fetchWithRetry()` 工具函数
- 对话 API (`callFastAPI`) 自动重试最多 3 次
- 语音转写 API (`transcribeAudio`) 自动重试最多 2 次
- 使用指数退避策略：100ms → 200ms → 400ms
- 不重试用户主动取消（AbortError）和客户端错误（4xx）

**验证方法**:
```bash
# 断开网络，发送消息，观察控制台重试日志
# 或者临时停止后端服务测试
```

**收益**:
- 网络抖动时自动恢复，无需用户手动重试
- 提升稳定性和用户体验

---

### 3. 后端速率限制 ✅
**文件**: 
- `mingjing-fastapi-proxy/requirements.txt` (添加 slowapi 依赖)
- `mingjing-fastapi-proxy/main.py` (初始化限流器)

**改动**:
- 聊天接口: 30次/分钟
- 语音转写: 10次/分钟
- 基于客户端 IP 地址限流
- 超限自动返回 429 状态码

**验证方法**:
```bash
# 安装依赖
cd mingjing-fastapi-proxy
pip install -r requirements.txt

# 快速发送多个请求测试限流
for i in {1..35}; do 
  curl -X POST http://127.0.0.1:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"messages":[{"role":"user","content":"test"}]}' & 
done
```

**收益**:
- 防止 API 被恶意或意外滥用
- 保护后端服务稳定性
- 控制 OpenAI API 成本

---

## 📊 影响评估

### 代码变更统计
- 新增文件: 2 个
  - `ErrorBoundary.jsx`
  - `TECH_DEBT_PROGRESS.md`
- 修改文件: 4 个
  - `main.jsx` (+3 行)
  - `aiClients.js` (+40 行重试逻辑)
  - `requirements.txt` (+1 依赖)
  - `main.py` (+7 行限流配置)

### 风险评估
- **前端**: ✅ 低风险
  - ErrorBoundary 仅作为安全网，不影响正常流程
  - fetchWithRetry 向后兼容，仅在失败时触发重试
  
- **后端**: ⚠️ 中风险
  - 速率限制可能影响高频用户，建议先设置宽松阈值
  - 建议监控 429 错误率，必要时调整限制

---

## 🔄 下一步计划

### 阶段二：结构重构（预计 1-2 周）
1. **提取 useSession Hook** - 会话管理逻辑
2. **提取 useBGM Hook** - 音频控制逻辑
3. **提取 useVoice Hook** - 语音交互逻辑
4. **重构 App.jsx** - 从 1619 行降到 <600 行

### 阶段三：质量保障（预计 1 周）
1. **单元测试** - useSession/useBGM/useVoice
2. **集成测试** - 竞态条件测试
3. **E2E 测试** - 关键用户路径

---

## 📝 备注

### Lint 警告
`main.py` 中存在 "Module level import not at top of file" 警告，这是因为需要先 `load_dotenv()` 再导入依赖环境变量的模块。这是常见模式，可以忽略。

### 依赖安装
重新部署时需要安装新依赖：
```bash
pip install -r requirements.txt
```

### 配置建议
- 生产环境建议调整速率限制：
  - VIP 用户可设置更高限额
  - 可通过环境变量 `RATE_LIMIT_CHAT` 和 `RATE_LIMIT_STT` 配置
