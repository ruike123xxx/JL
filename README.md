# Boss直聘自动招聘沟通机器人

RPA 做"手脚"(网页读取/输入/点击), Python 做"大脑"(拼 prompt / 调大模型 / 解析决策 / 维护会话状态)。

```
RPA 抓未读消息+对话+简历  ──HTTP POST──▶  Python 服务  ──▶  大模型
RPA 发送回复 / 发地址  ◀──JSON──  (answer + rpa_action)
```

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env      # 默认 LLM_PROVIDER=mock, 无需任何 API key
python run.py             # 启动在 http://127.0.0.1:8000
```

打开 http://127.0.0.1:8000/docs 可看交互式接口文档。

## 接口

### POST /rpa/conversation  (影刀第一步联调)

用于验证影刀已经成功抓取对话记录，并把文本传到本服务。该接口只返回接收回执，不调用大模型，不生成回复。

请求体:

```json
{
  "candidate_id": "boss_user_12345",
  "conversation": "影刀抓取的当前窗口全部可见对话文本"
}
```

响应体:

```json
{
  "candidate_id": "boss_user_12345",
  "received": true,
  "conversation_chars": 28,
  "stage": "初次接触",
  "next_endpoint": "/reply"
}
```

### POST /reply  (RPA 主接口)

请求体:

```json
{
  "candidate_id": "boss_user_12345",
  "conversation": "RPA 抓取的当前窗口全部可见对话文本",
  "resume": "候选人简历文本, 没有则传空字符串",
  "job_requirement": "岗位招聘需求",
  "company_info": "公司信息"
}
```

> `stage`(招聘阶段)不由 RPA 传, 由 Python 按 `candidate_id` 从 SQLite 读取/维护。

响应体:

```json
{
  "answer": "只有 rpa_action 为 reply_message 时这里才有内容",
  "reason": {
    "rpa_action": "reply_message | send_company_address",
    "basis": "依据说明"
  }
}
```

RPA 拿到后按 `reason.rpa_action` 分支：`reply_message` 表示发送 `answer`；`send_company_address` 表示发送地址且 `answer` 为空。索要简历由影刀主流程自行判断，不再由后端返回动作。

如果请求里带了 `resume`，后端会先做简历匹配评分。评分低于 60 分时，直接返回 `reply_message` 过滤话术，响应结构仍保持 `answer + reason`，不会把评分细节返回给影刀。

后端会校验大模型输出结构。如果模型没有返回标准 `answer + reason`，Python 会内部追加一次 JSON 修复调用；修复后仍不合规时返回固定兜底结构，影刀无需重复请求。

如果返回 `422 Unprocessable Entity`，说明请求体还没通过 FastAPI 校验，业务逻辑不会进入 `handle_reply()`。请确认影刀 HTTP 节点使用 `application/json`，并至少传入 `candidate_id`。

影刀 Python 请求示例：

```python
import requests
all_chat_text = "全部对话记录"
resume_person = "候选人简历"
job_requirement = "岗位招聘需求"
company_info = "公司信息"
payload = {
    "candidate_id": "test_001",
    "conversation": all_chat_text,
    "resume": resume_person,
    "job_requirement": job_requirement,
    "company_info": company_info,
}

headers = {
    "Content-Type": "application/json",
}

resp = requests.post(
    "http://127.0.0.1:8000/reply",
    json=payload,
    headers=headers,
)
```

### POST /resume/evaluate  (单独评价图片简历)

用于单独评价图片/视频简历。可以传影刀 OCR 后的 `resume_text`，也可以在阿里云 Qwen VL 模型配置好后传 `resume_image_url` 或 `resume_video_url`；该接口只返回评分详情，不生成聊天回复。

请求体:

```json
{
  "candidate_id": "boss_user_12345",
  "resume_text": "图片简历 OCR 后的文本内容",
  "resume_image_url": "图片简历 URL 或 data URL，三选一",
  "resume_video_url": "视频简历 URL 或 data URL，三选一",
  "job_requirement": "岗位招聘需求"
}
```

响应体:

```json
{
  "candidate_id": "boss_user_12345",
  "score": 72,
  "passed": true,
  "threshold": 60,
  "basis": "候选人具备财务相关经验，与岗位要求部分匹配",
  "matched": ["财务相关经验", "Excel能力"],
  "risks": ["工厂财务经验较弱"]
}
```

影刀 Python 请求示例：

```python
import requests

payload = {
    "candidate_id": "test_001",
    "resume_text": resume_person,
    "job_requirement": job_requirement,
}

resp = requests.post(
    "http://127.0.0.1:8000/resume/evaluate",
    json=payload,
)
```

如果要让 Qwen VL 直接读取图片，先把 `.env` 切到 `LLM_PROVIDER=aliyun`，然后传 `resume_image_url`：

```python
payload = {
    "candidate_id": "test_001",
    "resume_image_url": resume_image_url,
    "job_requirement": job_requirement,
}
```

如果要读取视频简历，传 `resume_video_url`：

```python
payload = {
    "candidate_id": "test_001",
    "resume_video_url": resume_video_url,
    "job_requirement": job_requirement,
}
```

### POST /reset  (调试用)

```json
{ "candidate_id": "boss_user_12345" }
```

清除该候选人会话状态, 联调时重来用。

## 验证

```bash
# 无简历 -> reply_message（索要简历由影刀主流程处理）
curl -X POST localhost:8000/reply -H "Content-Type: application/json" \
  -d '{"candidate_id":"t1","conversation":"你好，我想了解下这个岗位","resume":"","job_requirement":"Java后端","company_info":"某科技公司，单双休"}'

# 问地址 -> send_company_address
curl -X POST localhost:8000/reply -H "Content-Type: application/json" \
  -d '{"candidate_id":"t2","conversation":"面试地点在哪里？","resume":"5年Java","job_requirement":"Java后端","company_info":"某科技公司"}'

pytest tests/
```

## 切换到阿里云 Qwen 模型

阿里云百炼 DashScope 兼容 OpenAI Chat Completions 格式。改 `.env`:

```
LLM_PROVIDER=aliyun
LLM_API_KEY=你的阿里云百炼 API Key
LLM_MODEL=qwen3-vl-plus
LLM_VISION_MODEL=qwen3-vl-plus
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

`qwen3-vl-plus` 用于文本对话、评分以及图片/视频简历读取。若阿里云控制台模型名有更新，以控制台可用的 Qwen VL 视频模型为准。

## 目录

```
app/
├── main.py            FastAPI 入口
├── config.py          配置 (.env)
├── schemas.py         请求/响应模型 + RPA 动作枚举
├── api/routes.py      /reply, /rpa/conversation, /reset
├── api/resume_evaluation.py  /resume/evaluate
├── core/
│   ├── prompt.py      系统提示词模板 + 变量注入
│   ├── scoring.py     简历匹配评分 + 低分过滤
│   ├── json_repair.py 模型 JSON 容错解析
│   └── pipeline.py    主编排
├── llm/
│   ├── base.py        provider 抽象 + 工厂
│   ├── mock.py        假数据 (默认)
│   ├── aliyun.py      阿里云 Qwen provider
│   └── tongyi.py      真实模型骨架
└── store/db.py        SQLite 会话状态
```
