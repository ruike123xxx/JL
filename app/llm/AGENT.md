# app/llm/ — 大模型 provider 层（可插拔）

把"调哪个模型"与业务逻辑解耦。pipeline 只调抽象接口，不知道背后是 mock 还是真实模型。

## 文件

### base.py —— 抽象接口 + 工厂 + 重试
- `LLMProvider`（ABC）—— 统一接口，`generate(system, user, *, temperature=None) -> str`
- `post_with_retry(...)` —— 公共重试函数
- `get_provider()` —— `mock` → MockProvider；`aliyun` / `tongyi`(别名) → AliyunProvider

### mock.py —— 测试专用假数据 provider
不调真实模型。用于 pytest 与本地无 key 场景：
- 评分 prompt → 返回关键词匹配评分 JSON
- 聊天 prompt → 按关键词返回不同 `rpa_action` 分支

**生产环境不使用 mock。**

### aliyun.py —— 生产 LLM provider
调 OpenAI 兼容 Chat Completions 接口（阿里云百炼、DeepSeek 等）。
- 文本对话、简历评分走 `generate()`
- 视觉能力保留在 provider 内，供后续扩展

## 新增 provider
1. 新建 `app/llm/<name>.py`，继承 `LLMProvider`
2. 在 [base.py](base.py) 的 `get_provider()` 注册
3. `.env` 设 `LLM_PROVIDER=<name>`
