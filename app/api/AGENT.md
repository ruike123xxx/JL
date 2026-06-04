# app/api/ — HTTP 路由层

RPA 与本服务的唯一接触面。只做"收请求 → 调 pipeline → 回响应"，不写业务逻辑。

## 文件

### routes.py
定义 `router`（APIRouter），由 [app/main.py](../main.py) 挂载。

- **`POST /reply`** —— RPA 主接口。
  - 入参：`ReplyRequest`（见 [app/schemas.py](../schemas.py)）
  - 出参：`ReplyResponse`（answer + reason，只有 `rpa_action=reply_message` 时 answer 有内容）
  - 实现：直接委托给 [app/core/pipeline.py](../core/pipeline.py) 的 `handle_reply()`
  - RPA 用法：按 `reason.rpa_action` 分支；`reply_message` 发送 `answer`，其它动作执行影刀预设流程

- **`POST /rpa/conversation`** —— 影刀第一步联调接口。
  - 入参：`ConversationIngestRequest`（candidate_id / conversation）
  - 出参：`ConversationIngestResponse`（received / conversation_chars / stage / next_endpoint）
  - 只确认本服务收到影刀上传的对话文本，不调用大模型、不生成回复

- **`POST /reset`** —— 调试用。
  - 入参：`ResetRequest`（candidate_id）
  - 清除该候选人会话状态（调 [app/store/db.py](../store/db.py) 的 `reset_session`）
  - 返回 `{candidate_id, deleted}`，联调重来用

## 改这里的时机
- 新增 RPA 调用的接口（如批量回复、查询会话状态）
- 调整请求/响应字段（同时改 [app/schemas.py](../schemas.py)）

**不要**在这里写决策/拼 prompt/调模型逻辑——那些属于 [app/core/](../core/)。
