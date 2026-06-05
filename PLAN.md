# PLAN.md — 后续待办与补充清单

> 当前状态：骨架已完成并验证通过（mock 模型 + SQLite + FastAPI，`pytest` 5 项全过，HTTP 端到端冒烟通过）。
> 本文件记录接下来要做的事，按优先级排列。

---

## P0 — 让机器人真正能用

### 1. 接入真实国产模型
- [ ] 选定模型家（通义 qwen / 豆包 / DeepSeek），申请 API key
- [ ] `.env` 设 `LLM_PROVIDER=tongyi`、填 `LLM_API_KEY`、确认 `LLM_BASE_URL`/`LLM_MODEL`
- [ ] 实测 [app/llm/tongyi.py](app/llm/tongyi.py)：确认返回能被 `json_repair` 正确解析
- [ ] 个别模型不支持 `response_format={"type":"json_object"}` 时，去掉该行并依赖 `json_repair` 兜底
- [ ] 加超时重试（httpx 偶发超时、限流 429）与失败兜底（返回安全的人工接管提示）

### 2. RPA 端对接联调
- [ ] RPA 流程加 HTTP POST 节点指向 `localhost:8000/reply`
- [ ] 验证 RPA 能稳定抓取「当前窗口全部可见对话」并正确填入 `conversation`
- [ ] 验证 RPA 按 `reason.rpa_action` 分支：reply_message 发送 answer，send_company_address 执行预设动作；索要简历由影刀主流程处理
- [ ] 确认中文经 HTTP 往返无乱码（终端乱码是显示问题，HTTP 数据为 UTF-8）

---

## P1 — 提升回复质量与稳定性

### 3. stage 招聘阶段状态机细化
- [ ] 当前是简单映射（[app/core/pipeline.py](app/core/pipeline.py) 的 `_STAGE_BY_ACTION`）
- [ ] 细化为：`初次接触 → 意向确认 → 约面中 → 已约面 → 已结束`
- [ ] 把 stage 作为上下文更明确地喂给模型，让不同阶段回复策略不同
- [ ] 防回退：已约面不应因一句闲聊退回初次接触

### 4. 简历处理增强
- [ ] 当前后端不再判断是否索要简历；若需结合简历内容提问，确认 RPA 抓取的简历文本质量
- [ ] （可选）若 RPA 难以抓全，改为 Python 解析简历 PDF（加 pdfplumber 依赖，需传文件路径）

### 5. 提示词迭代
- [ ] 用真实对话回归测试提示词 [app/core/prompt.py](app/core/prompt.py)
- [ ] 补充合规边界用例（拒答婚育/年龄/薪资承诺等），加入测试断言
- [ ] 调 temperature / 增加 few-shot 示例稳定 JSON 输出

---

## P2 — 工程化与运维

### 6. 日志与可观测
- [ ] 记录每次 `/reply` 的输入、模型原始返回、解析结果（便于排查与提示词调优）
- [ ] 区分日志级别；模型解析失败、provider 异常单独告警

### 7. 频率与合规风控（避免被平台判定为机器人）
- [ ] 回复间隔随机延迟（在 RPA 端或服务端控制）
- [ ] 单候选人/单日回复次数上限
- [ ] 敏感场景（如薪资谈判、明确拒绝）转人工，不自动回复

### 8. 多轮对话去重
- [ ] RPA 每轮抓全量对话，需避免对同一条候选人消息重复回复
- [ ] 方案：记录上次已回复的「对话指纹/最后一条消息」，无新消息则不触发

### 9. 测试与 CI
- [ ] 为 `json_repair` 增加更多脏数据用例（markdown 包裹、字段缺失、reason 为字符串、非法 action）
- [ ] 为 stage 状态机迁移加测试
- [ ] （可选）GitHub Actions 跑 pytest

---

## P3 — 可选扩展

- [ ] 多岗位支持：一个机器人服务多个在招岗位（请求体带 `job_id`，job_requirement 从配置/库读取）
- [ ] 管理界面：查看会话状态、人工接管、修改提示词
- [ ] 数据库迁移到 MySQL/Postgres（仅需改 [app/store/db.py](app/store/db.py)，接口已隔离）
- [ ] Prompt caching / batch（若模型支持）降本

---

## 已知技术点备忘

- **数据库**：SQLite 本地文件 `sessions.db`，零部署，自动建表。换数据库只改 [app/store/db.py](app/store/db.py)。
- **模型可插拔**：新增 provider = 加一个 `app/llm/xxx.py` + 在 [app/llm/base.py](app/llm/base.py) 的 `get_provider()` 注册。
- **JSON 容错**：[app/core/json_repair.py](app/core/json_repair.py) 永不抛错，最差返回人工接管兜底。
- **stage 不由 RPA 传**：由 Python 按 `candidate_id` 维护。
