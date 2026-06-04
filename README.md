# Boss直聘自动招聘沟通机器人

RPA 做"手脚"(网页读取/输入/点击), Python 做"大脑"(拼 prompt / 调大模型 / 解析决策 / 维护会话状态)。

```
RPA 抓未读消息+对话+简历  ──HTTP POST──▶  Python 服务  ──▶  大模型
RPA 发送回复 / 索要简历 / 发地址  ◀──JSON──  (answer + rpa_action)
```

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env      # 默认 LLM_PROVIDER=mock, 无需任何 API key
python run.py             # 启动在 http://127.0.0.1:8000
```

打开 http://127.0.0.1:8000/docs 可看交互式接口文档。

## 接口

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
  "answer": "给候选人的回复内容",
  "reason": {
    "reply_intent": "索要简历/推进面试/补充岗位信息/确认匹配度",
    "rpa_action": "request_resume | send_company_address | confirm_interview_time | none",
    "basis": "依据说明"
  }
}
```

RPA 拿到后: **先发送 `answer`, 再用 if 判断 `reason.rpa_action` 决定是否执行后续动作**(索要简历、发地址、约面)。

### POST /reset  (调试用)

```json
{ "candidate_id": "boss_user_12345" }
```

清除该候选人会话状态, 联调时重来用。

## 验证

```bash
# 无简历 -> request_resume
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
LLM_MODEL=qwen-plus
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

换 DeepSeek/豆包通常只改这三行(base_url/model/key), 代码无需改动。详见 [app/llm/tongyi.py](app/llm/tongyi.py)。

## 目录

```
app/
├── main.py            FastAPI 入口
├── config.py          配置 (.env)
├── schemas.py         请求/响应模型 + RPA 动作枚举
├── api/routes.py      /reply, /reset
├── core/
│   ├── prompt.py      系统提示词模板 + 变量注入
│   ├── json_repair.py 模型 JSON 容错解析
│   └── pipeline.py    主编排
├── llm/
│   ├── base.py        provider 抽象 + 工厂
│   ├── mock.py        假数据 (默认)
│   └── tongyi.py      真实模型骨架
└── store/db.py        SQLite 会话状态
```
