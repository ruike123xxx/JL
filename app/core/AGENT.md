# app/core/ — 业务核心

机器人的"大脑"。拼提示词、调模型、解析决策、编排全流程。改回复逻辑主要在这里。

## 文件

### pipeline.py —— 主编排
`handle_reply(req: ReplyRequest) -> ReplyResponse`，串起整条链路：
1. `db.get_or_default()` 读会话状态（stage / 历史简历）
2. 合并简历：本轮有则用本轮并更新；本轮空则复用库里的
3. `score_resume()` 对已有简历先评分；低于 60 分直接返回过滤话术
4. `prompt.build_messages()` 拼 system + user
5. `get_provider().generate()` 调模型
6. `parse_reply_result()` 校验解析；结构不合规时用 `build_repair_messages()` 追加一次 JSON 修复调用
7. 修复后仍不合规 → 返回固定兜底 `ReplyResponse`
8. `db.upsert_session()` 更新 stage + 简历快照
- `_STAGE_BY_ACTION` —— rpa_action → 新 stage 的简单映射。**stage 状态机要细化就改这里**（见 [PLAN.md](../../PLAN.md) P1）。

### scoring.py —— 简历评分
- `score_resume(resume, job_requirement) -> ResumeScore` —— 有简历时先做 0-100 分匹配评分。
- `SCORE_PASS_THRESHOLD` —— 当前通过阈值为 `60` 分。
- `LOW_SCORE_MESSAGE` —— 低分候选人返回给影刀发送的话术；返回结构仍是 `ReplyResponse`，不暴露 score 字段。
- `mock` provider 下用关键词启发式评分；真实 provider 下用独立评分 prompt 调模型。
- 同时供 `POST /resume/evaluate` 单独评价图片/视频简历使用；可传 OCR 文本、图片 URL 或视频 URL（需支持视觉/视频的 provider）。

### prompt.py —— 提示词模板 + 变量注入
- `SYSTEM_PROMPT` —— HR 助手系统提示词（角色、目标、合规边界、rpa_action 取值、输出 JSON 格式）。**调回复风格/规则改这里。**
- `USER_TEMPLATE` —— 用户提示词模板，含 5 个占位：`{{conversation}}` `{{job_requirement}}` `{{resume}}` `{{company_info}}` `{{stage}}`
- `build_messages(...)` —— 用**普通字符串替换**（非 `str.format`）注入变量，避免简历/对话里出现 `{ }` 时报错。返回 `(system, user)`。
  - 注意：`resume` 为空时保留空串；索要简历由影刀主流程处理，后端不再返回索要简历动作。

### json_repair.py —— 模型 JSON 容错解析
模型返回不可信（markdown 包裹 / 前后加文字 / 字段缺失 / 非法 action），这里负责"永不抛错地"解析。
- `_extract_json(text)` —— 去 ```json 围栏 → 直接 `json.loads` → 失败则正则抠第一个 `{...}` 块
- `parse_reply_result(raw) -> ParsedReply` —— 解析 + 校验 + 补默认值，并标记原始输出是否合规：
  - `rpa_action` 不在 `RPA_ACTIONS` 内 → 归一为 `reply_message`
  - `rpa_action` 不是 `reply_message` 时 → 强制清空 `answer`
  - 兼容 `reason` 为字符串的"最简版"输出
  - 彻底解析失败 → 标记为不合规并返回安全的人工接管兜底文案
- `build_repair_messages(raw)` —— 构造一次性 JSON 修复 Prompt，只修复模型原始输出，不用原参数重跑业务 Prompt。
- **这是纯 RPA 几乎做不到、而 Python 必须做的关键模块。**

## 测试
端到端测试在 [tests/test_reply.py](../../tests/test_reply.py)，用 mock provider 跑通 `/reply`，断言：
返回结构、低分简历→过滤话术、模型输出不合规→一次修复/兜底、无简历仍走 reply_message、问地址→send_company_address、rpa_action 始终合法、reset 生效。
脏数据解析用例待补（见 [PLAN.md](../../PLAN.md) P2 第 9 项）。

## 改这里的时机
- 调回复风格/规则/合规边界 → `prompt.py`
- 调简历评分阈值/低分话术/评分规则 → `scoring.py`
- 加新的解析容错场景 → `json_repair.py`
- 改编排顺序 / stage 推进逻辑 → `pipeline.py`
