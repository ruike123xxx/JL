# app/ — 应用根目录

顶层装配与配置。具体业务在子目录（api / core / llm / store）。

## 文件

### main.py
FastAPI 应用入口。
- 创建 `app` 实例，注册 [api/routes.py](api/routes.py) 的路由。
- `lifespan`：启动时调用 `db.init_db()` 建表。
- 注册 `RequestValidationError` 处理器，让影刀请求体不符合接口时返回清晰的 422 调试提示。
- 暴露 `GET /health` 健康检查。
- `run.py` 通过 `app.main:app` 启动它。

### config.py
集中配置，基于 `pydantic-settings`，从环境变量 / `.env` 读取。
- `settings` 单例：全项目通过 `from app.config import settings` 取配置。
- 关键项：
  - `host` / `port` — 服务监听地址
  - `llm_provider` — `mock`（默认）或 `tongyi`，决定用哪个模型 provider
  - `llm_api_key` / `llm_model` / `llm_base_url` — 真实模型配置
  - `db_path` — SQLite 文件路径（默认 `sessions.db`）
- 改默认值看这里；改运行值改 `.env`（模板见 `.env.example`）。

### schemas.py
全项目的 Pydantic 数据模型 + 枚举。**新增字段/动作的源头在这里。**
- `RPA_ACTIONS` — 合法 RPA 动作集合：`reply_message` / `send_company_address`。新增动作必须先改这里。
- `DEFAULT_STAGE` — 默认招聘阶段 `"初次接触"`。
- `ReplyRequest` — RPA 发来的请求体（candidate_id / conversation / resume / job_requirement / company_info）。注意 **不含 stage**。
- `ReplyReason` — 模型输出的结构化动作与依据（rpa_action / basis）。
- `ReplyResponse` — 返回给 RPA 的响应体（answer + reason），只有 `rpa_action=reply_message` 时 answer 有内容。
- `ConversationIngestRequest` / `ConversationIngestResponse` — 影刀第一步上传对话文本的请求与回执。
- `ResetRequest` — `/reset` 请求体。

## 子目录
- [api/](api/) — HTTP 路由
- [core/](core/) — 业务核心
- [llm/](llm/) — 模型 provider
- [store/](store/) — 数据存储
