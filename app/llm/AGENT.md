# app/llm/ — 大模型 provider 层（可插拔）

把"调哪个模型"与业务逻辑解耦。pipeline 只调抽象接口，不知道背后是 mock 还是真实模型。
**DeepSeek/通义/豆包等 OpenAI 兼容模型通常只改 `.env`；新增非兼容模型才加 provider 文件并在 base.py 注册。**

## 文件

### base.py —— 抽象接口 + 工厂
- `LLMProvider`（ABC）—— 统一接口，唯一方法 `generate(system: str, user: str) -> str`，返回模型**原始文本**（期望是 JSON 字符串，解析交给 [core/json_repair.py](../core/json_repair.py)）。
- `get_provider() -> LLMProvider` —— 按 `settings.llm_provider` 选实例：`mock` → `MockProvider`，`tongyi` → `TongyiProvider`（OpenAI 兼容接口，可接 DeepSeek/通义/豆包），未知值抛错。
  - **新增 provider 在这里注册一个分支。**

### mock.py —— 假数据 provider（默认启用）
不调任何真实模型，按 user 提示词内容做简单关键词规则，返回结构合法的假 JSON，让 RPA 联调时能看到不同分支：
- 含"地址/面试地点/怎么去/在哪/到场" → `send_company_address`
- 其它 → `reply_message`

只有 `reply_message` 会返回非空 `answer`；`send_company_address` 的 `answer` 为空，由影刀执行预设动作。索要简历由影刀主流程处理。

用于无 key 联调与单元测试。**改 mock 行为不影响真实模型逻辑。**

### tongyi.py —— OpenAI 兼容真实模型 provider（骨架）
`TongyiProvider.generate()` 用 `httpx` 打 **OpenAI 兼容**的 Chat Completions 接口。
通义/豆包/DeepSeek 大多兼容此格式，换家通常只改 `.env` 的 `LLM_BASE_URL`/`LLM_MODEL`/`LLM_API_KEY`，**代码不动**。
- 读 `settings.llm_api_key/llm_model/llm_base_url`
- 发 `system + user` 两条消息，请求 `response_format={"type":"json_object"}`
- 取 `choices[0].message.content` 返回
- 待补（见 [PLAN.md](../../PLAN.md) P0 第 1 项）：超时重试、429 限流处理、失败兜底；个别模型不支持 json_object 时去掉该参数靠 json_repair 兜底。

## 新增一个 provider 的步骤
1. 新建 `app/llm/<name>.py`，写一个继承 `LLMProvider` 的类，实现 `generate()`
2. 在 [base.py](base.py) 的 `get_provider()` 加分支
3. `.env` 设 `LLM_PROVIDER=<name>` 及所需 key
