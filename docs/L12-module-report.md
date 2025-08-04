# L12 模块完成度报告：伪频响应回收（优雅中止优化）

**模块编号**：L12  
**目标功能**：优化伪频检测触发后的用户体验，实现优雅中止与状态事件上报。

---

## 功能概述

- **原目标**

  1. 在伪频检测触发时，不仅返回错误信息，还应输出 `recycle_event` 状态字段。
  2. 为未来流式输出中止优化预留接口（当前仅实现非流式）。

- **已实现**

  - 非流式模式下，当伪频触发时：
    - 返回 `message` = 自毁提示文案
    - 增加 `recycle_event = { triggered: true, reason: "伪频检测触发回收" }`
  - `/v1/test/all` 中新增 **recycle** 结果展示：
    ```json
    "recycle_event": {
      "triggered": true,
      "reason": "伪频检测触发回收"
    }
    ```
  - 日志中打印事件触发原因，便于调试。

- **未完成**
  - 流式输出的即时中止与事件推送（预留接口，未集成）。

---

## 代码文件清单

- **核心实现**

  - `core/recycler.py`：新增模块，封装 `trigger_recycle_event(reason)`
  - `main.py`：调用 `recycle_event` 并在 `/v1/test/all` 报告中输出

- **相关依赖**
  - 与 `core/detector.py`（伪频检测）联动
  - 与 `core/firewall.py`、`core/frequency.py`、`core/verifier.py` 共用测试框架

---

## 测试状态

### 统一测试 `/v1/test/all`

- 签名验证：**通过**
- 频率偏移：**通过**
- 防火墙：**通过**
- 伪频检测：**通过**
- 回收事件：**触发并正确显示**

示例输出片段：

````json
"recycle_event": {
  "triggered": true,
  "reason": "伪频检测触发回收"
}

# L12 模块完成度报告：伪频响应回收（优雅中止优化）

**模块编号**：L12
**目标功能**：优化伪频检测触发后的用户体验，实现优雅中止与状态事件上报。

---

## 功能概述

- **原目标**
  1. 在伪频检测触发时，不仅返回错误信息，还应输出 `recycle_event` 状态字段。
  2. 为未来流式输出中止优化预留接口（当前仅实现非流式）。

- **已实现**
  - 非流式模式下，当伪频触发时：
    - 返回 `message` = 自毁提示文案
    - 增加 `recycle_event = { triggered: true, reason: "伪频检测触发回收" }`
  - `/v1/test/all` 中新增 **recycle** 结果展示：
    ```json
    "recycle_event": {
      "triggered": true,
      "reason": "伪频检测触发回收"
    }
    ```
  - 日志中打印事件触发原因，便于调试。

- **未完成**
  - 流式输出的即时中止与事件推送（预留接口，未集成）。

---

## 代码文件清单

- **核心实现**
  - `core/recycler.py`：新增模块，封装 `trigger_recycle_event(reason)`
  - `main.py`：调用 `recycle_event` 并在 `/v1/test/all` 报告中输出

- **相关依赖**
  - 与 `core/detector.py`（伪频检测）联动
  - 与 `core/firewall.py`、`core/frequency.py`、`core/verifier.py` 共用测试框架

---

## 测试状态

### 统一测试 `/v1/test/all`
- 签名验证：**通过**
- 频率偏移：**通过**
- 防火墙：**通过**
- 伪频检测：**通过**
- 回收事件：**触发并正确显示**

示例输出片段：
```json
"recycle_event": {
  "triggered": true,
  "reason": "伪频检测触发回收"
}
````
