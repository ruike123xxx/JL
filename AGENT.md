# AGENT.md — 项目总索引

> 本文件是给 AI agent / 开发者的导航索引。每个子目录下另有 `AGENT.md` 描述该目录内文件的具体功能。
> 详细的设计背景见 [README.md](README.md)，后续待办见 [PLAN.md](PLAN.md)。

## 这个项目是什么

Boss直聘自动招聘沟通机器人的**后端大脑**。
RPA 做"手脚"（网页读取/输入/点击），本项目（Python）做"大脑"（拼 prompt / 调大模型 / 解析决策 / 维护会话状态）。

```
RPA 抓未读消息+对话+简历  ──HTTP POST /reply──▶  本项目  ──▶  大模型
RPA 发送回复 / 发地址  ◀──JSON(answer+rpa_action)──  本项目
```

影刀第一步联调用 `POST /rpa/conversation`，只上传并确认收到对话文本，不触发大模型；正式生成回复仍用 `POST /reply`。

## 一次 /reply 请求的完整数据流

```
RPA POST /reply
  → app/api/routes.py        接收请求 (ReplyRequest)
  → app/core/pipeline.py     主编排:
       1. app/store/db.py        读会话状态 (stage / 历史简历)
       2. 合并简历 (本轮 or 库里)
       3. app/core/scoring.py    有简历时先做匹配评分，低于 60 分直接过滤
       4. app/core/prompt.py     拼 system + user 提示词
       5. app/llm/base.py        按配置取 provider
          app/llm/mock.py         (默认) 返回假 JSON
          app/llm/tongyi.py       (可选) 调 OpenAI 兼容真实模型
       6. app/core/json_repair.py 容错解析模型返回 → ReplyResponse
       7. app/store/db.py        更新 stage + 简历快照
  → 返回 JSON (answer + reason.rpa_action) 给 RPA，只有 reply_message 时 answer 有内容
```

## 目录索引

| 路径 | 作用 | 详细说明 |
|------|------|----------|
| [run.py](run.py) | 启动入口 (`python run.py`) | — |
| [config.py](app/config.py) | 集中配置 (读 .env) | 见 [app/AGENT.md](app/AGENT.md) |
| [schemas.py](app/schemas.py) | 请求/响应模型 + RPA 动作枚举 | 见 [app/AGENT.md](app/AGENT.md) |
| [app/main.py](app/main.py) | FastAPI 入口 | 见 [app/AGENT.md](app/AGENT.md) |
| [app/api/](app/api/) | HTTP 路由层（`/rpa/conversation`、`/reply`、`/reset`） | 见 [app/api/AGENT.md](app/api/AGENT.md) |
| [app/core/](app/core/) | 业务核心：prompt / 解析 / 编排 | 见 [app/core/AGENT.md](app/core/AGENT.md) |
| [app/llm/](app/llm/) | 大模型 provider 层（可插拔） | 见 [app/llm/AGENT.md](app/llm/AGENT.md) |
| [app/store/](app/store/) | SQLite 会话状态存储 | 见 [app/store/AGENT.md](app/store/AGENT.md) |
| [tests/](tests/) | 端到端测试 | 见 [app/core/AGENT.md](app/core/AGENT.md) 末尾 |

## 关键约束（改代码前必读）

- **职责边界**：RPA 只读写网页，Python 负责所有"思考"。不要把决策逻辑推回 RPA。
- **`rpa_action` 是机器可读枚举**：合法值定义在 [app/schemas.py](app/schemas.py) 的 `RPA_ACTIONS`（`reply_message` / `send_company_address`）。新增动作必须同时改这里和 mock/真实 prompt。
- **`stage` 不由 RPA 传**：由 Python 按 `candidate_id` 从 SQLite 维护。
- **模型可插拔**：DeepSeek/通义/豆包等 OpenAI 兼容模型通常只改 `.env`，新增非兼容模型再加 `app/llm/xxx.py`，业务逻辑（pipeline）不感知具体模型。
- **影刀执行动作**：Python 只返回 `rpa_action`，影刀按返回值用 if 分支执行发消息、发地址；索要简历由影刀主流程自行处理。
- **简历评分先行**：已有简历时先评分，低于 60 分直接返回过滤话术；评分细节暂不返回给影刀。
- **JSON 解析永不抛错**：[app/core/json_repair.py](app/core/json_repair.py) 最差返回人工接管兜底。
- **数据库是 SQLite 本地文件**：零部署，自动建表。换数据库只改 [app/store/db.py](app/store/db.py)。

## 常用命令

```bash
python run.py            # 启动服务 (默认 mock provider, 无需 key)
pytest tests/            # 跑测试
# 接口文档: http://127.0.0.1:8000/docs
```
