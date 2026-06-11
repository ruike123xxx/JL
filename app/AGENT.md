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
- 关键项：
  - `host` / `port` — 服务监听地址
  - `llm_provider` — 生产用 `aliyun`；`mock` 仅 pytest；`tongyi` 为 aliyun 别名
  - `llm_api_key` / `llm_model` / `llm_vision_model` / `llm_base_url` — 模型配置
  - `db_path` — SQLite 文件路径（默认 `sessions.db`）

### schemas.py
全项目的 Pydantic 数据模型 + 枚举。
- `RPA_ACTIONS` — `reply_message` / `send_company_address`
- `STAGES` / `DEFAULT_STAGE` — 招聘阶段状态机
- `ReplyRequest` / `ReplyResponse` / `ReplyReason` — `/reply` 请求与响应
- `ResetRequest` — `/reset` 请求体

## 子目录
- [api/](api/) — HTTP 路由
- [core/](core/) — 业务核心
- [llm/](llm/) — 模型 provider
- [store/](store/) — 数据存储
