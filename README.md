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

如果返回 `422 Unprocessable Entity`，说明请求体还没通过 FastAPI 校验，业务逻辑不会进入 `handle_reply()`。请确认影刀 HTTP 节点使用 `application/json`，并至少传入 `candidate_id`。

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

## 切换到真实模型

国产模型(通义/豆包/DeepSeek)大多兼容 OpenAI Chat Completions 格式。改 `.env`:

```
LLM_PROVIDER=tongyi
LLM_API_KEY=你的key
LLM_MODEL=deepseek-v4-pro
LLM_BASE_URL=https://api.deepseek.com
```

`tongyi` 这里实际是 OpenAI 兼容接口 provider；换通义/豆包通常只改 base_url/model/key，代码无需改动。详见 [app/llm/tongyi.py](app/llm/tongyi.py)。

## 目录

```
app/
├── main.py            FastAPI 入口
├── config.py          配置 (.env)
├── schemas.py         请求/响应模型 + RPA 动作枚举
├── api/routes.py      /reply, /reset
├── core/
│   ├── prompt.py      系统提示词模板 + 变量注入
│   ├── scoring.py     简历匹配评分 + 低分过滤
│   ├── json_repair.py 模型 JSON 容错解析
│   └── pipeline.py    主编排
├── llm/
│   ├── base.py        provider 抽象 + 工厂
│   ├── mock.py        假数据 (默认)
│   └── tongyi.py      真实模型骨架
└── store/db.py        SQLite 会话状态
```
