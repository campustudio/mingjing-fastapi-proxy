# 阶段二重构进度

## ✅ 已完成

### 1. Hook提取

#### useSession.js ✓
**负责**: 会话管理逻辑
**提取内容**:
- 会话状态（sessions, currentSessionId, messages）
- 消息缓存（messagesCacheRef）
- 竞态防护（sessionFetchSeqRef）
- 会话操作（创建、切换、重命名、删除）
- 会话置顶逻辑

**代码行数**: 244行

**关键特性**:
- ✅ 序列号防竞态覆盖
- ✅ 本地缓存优先显示
- ✅ 后台重试机制（重命名）
- ✅ 30秒内置顶逻辑
- ✅ 支持回调扩展（extraActions）

---

#### useBGM.js ✓
**负责**: 背景音乐控制
**提取内容**:
- BGM状态（enabled, volume, isPlaying, userPaused）
- WebAudio管线（AudioContext, GainNode, DynamicsCompressor）
- 播放控制（play, pause, toggle）
- 录音期间暂停/恢复
- 移动端兼容（静默prime、手势解锁）

**代码行数**: 342行

**关键特性**:
- ✅ WebAudio精细控制
- ✅ 淡入淡出效果
- ✅ 录音期间自动暂停
- ✅ 2秒延迟恢复
- ✅ 用户手动暂停优先级
- ✅ 移动端音频策略兼容

---

#### useVoice.js ✓
**负责**: 语音录音和可视化
**提取内容**:
- 录音状态（isRecording, transcribing）
- 音量等化条（levels）
- 波形绘制（Canvas右→左滚动）
- 录音状态边沿检测

**代码行数**: 178行

**关键特性**:
- ✅ 实时波形绘制
- ✅ 指数平滑音量
- ✅ 转写最小显示时长（1秒）
- ✅ requestAnimationFrame优化
- ✅ 状态自动管理

---

## 🔄 进行中

### 2. 重构 App.jsx

**目标**: 从 1619行 减少到 <600行

**策略**:
1. 替换会话管理逻辑为 `useSession`
2. 替换BGM控制为 `useBGM`
3. 替换语音逻辑为 `useVoice`
4. 清理冗余状态和ref
5. 简化事件处理逻辑
6. 保留UI渲染和业务逻辑

**预计删除**:
- ~500行会话管理代码
- ~400行BGM控制代码
- ~200行语音处理代码
- ~100行ref和状态定义

**保留**:
- UI组件渲染（~400行）
- 登录逻辑（~50行）
- 主题切换（~30行）
- 消息发送（使用现有的 useMessageSender）
- 其他业务逻辑

---

## 📋 重构清单

### Step 1: 导入新Hook ✓
```javascript
import { useSession } from './hooks/useSession';
import { useBGM } from './hooks/useBGM';
import { useVoice } from './hooks/useVoice';
```

### Step 2: 替换状态定义
- [ ] 移除会话相关state（由useSession管理）
- [ ] 移除BGM相关state（由useBGM管理）
- [ ] 移除语音相关state（由useVoice管理）

### Step 3: 调用Hook
- [ ] 初始化 useSession
- [ ] 初始化 useBGM
- [ ] 初始化 useVoice
- [ ] 传递必要的参数和回调

### Step 4: 更新事件处理
- [ ] 会话操作调用Hook方法
- [ ] BGM控制调用Hook方法
- [ ] 语音控制调用Hook方法
- [ ] 移除冗余的useEffect/useCallback

### Step 5: 更新组件props
- [ ] VoiceButton接收Voice Hook返回值
- [ ] SideNav接收Session Hook返回值
- [ ] 其他组件更新

### Step 6: 测试验证
- [ ] 会话功能正常
- [ ] BGM播放/暂停正常
- [ ] 语音录音正常
- [ ] 所有交互无回归

---

## 📊 预期效果

| 指标 | 重构前 | 重构后 | 改善 |
|------|--------|--------|------|
| App.jsx行数 | 1619行 | <600行 | ↓63% |
| 可读性 | ⭐⭐ | ⭐⭐⭐⭐⭐ | 大幅提升 |
| 可维护性 | 低 | 高 | 显著改善 |
| 可测试性 | 困难 | 容易 | Hook可独立测试 |
| 代码复用 | 无 | 高 | Hook可跨组件复用 |

---

## 🎯 下一步

1. **重构App.jsx** - 使用新Hook
2. **测试验证** - 确保无功能回归
3. **优化调整** - 根据实际情况微调
4. **文档更新** - 更新README和注释
5. **Git提交** - 创建阶段二完成tag

---

## ⚠️ 注意事项

1. **保持功能等价** - 不改变业务逻辑
2. **渐进式重构** - 一次只改一个Hook
3. **频繁测试** - 每次改动后立即测试
4. **保留备份** - Git commit before each step
5. **性能监控** - 确保无性能下降
