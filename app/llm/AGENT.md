# app/llm/ — 大模型 provider 层（可插拔）

把"调哪个模型"与业务逻辑解耦。pipeline 只调抽象接口，不知道背后是 mock 还是真实模型。
**阿里云 Qwen 用 `aliyun` provider；DeepSeek/通义/豆包等 OpenAI 兼容模型通常只改 `.env`；新增非兼容模型才加 provider 文件并在 base.py 注册。**

## 文件

### base.py —— 抽象接口 + 工厂 + 重试
- `LLMProvider`（ABC）—— 统一接口，`generate(system, user, *, temperature=None) -> str`，返回模型**原始文本**（期望是 JSON 字符串，解析交给 [core/json_repair.py](../core/json_repair.py)）。`temperature` 为 `None` 时用默认主回复温度；评分/修复等结构化场景显式传 `settings.llm_temperature_structured`（低温更稳定）。
- `post_with_retry(...)` —— 公共重试函数：429 读 `Retry-After`、5xx/超时/网络抖动指数退避，可重试错误才重试，4xx 立即抛 `LLMError`，重试耗尽抛 `LLMUnavailableError`。所有真实 provider 都走这里。**重试/超时/退避参数在 `.env`（`LLM_TIMEOUT`/`LLM_MAX_RETRIES`/`LLM_RETRY_BACKOFF`）。**
- 模块级 `httpx.Client` 连接池复用，避免每次请求重新握手。
- `LLMError` / `LLMUnavailableError` —— 模型异常基类与"不可用"异常；pipeline 捕获后降级为兜底，`/reply` 永不 500。
- `get_provider() -> LLMProvider` —— 按 `settings.llm_provider` 选实例：`mock` → `MockProvider`，`tongyi` → `TongyiProvider`，`aliyun` → `AliyunProvider`，未知值抛错。
  - **新增 provider 在这里注册一个分支。**

### mock.py —— 假数据 provider（默认启用）
不调任何真实模型，按 user 提示词内容做简单关键词规则，返回结构合法的假 JSON（含 `reason.next_stage`），让 RPA 联调时能看到不同分支与阶段推进：
- 含"地址/面试地点/怎么去/在哪/到场" → `send_company_address`，next_stage=`已结束`
- 含"不感兴趣/已入职/已找到/不考虑/暂时不" → `reply_message` 礼貌收尾，next_stage=`已结束`（退出复用 reply_message）
- 含"面试/约时间/什么时候/时间" → `reply_message`，next_stage=`邀约`
- 其它 → `reply_message`，next_stage=`了解动机`

只有 `send_company_address` 的 `answer` 为空（由影刀执行预设动作），其余分支 answer 非空。索要简历由影刀主流程处理。

用于无 key 联调与单元测试。**改 mock 行为不影响真实模型逻辑。**

### tongyi.py —— OpenAI 兼容真实模型 provider（骨架）
`TongyiProvider.generate()` 用 `httpx` 打 **OpenAI 兼容**的 Chat Completions 接口。
通义/豆包/DeepSeek 大多兼容此格式，换家通常只改 `.env` 的 `LLM_BASE_URL`/`LLM_MODEL`/`LLM_API_KEY`，**代码不动**。
- 读 `settings.llm_api_key/llm_model/llm_base_url`
- 发 `system + user` 两条消息，请求 `response_format={"type":"json_object"}`
- 取 `choices[0].message.content` 返回
- 通过 `base.post_with_retry()` 自动获得超时重试/429/5xx 容错；个别模型不支持 json_object 时去掉该参数靠 json_repair 兜底。

### aliyun.py —— 阿里云 Qwen provider
`AliyunProvider.generate()` 调阿里云百炼 DashScope OpenAI 兼容 Chat Completions 接口。
- 文本模型默认建议：`LLM_MODEL=qwen3-vl-plus`
- 视觉/视频模型默认建议：`LLM_VISION_MODEL=qwen3-vl-plus`
- `generate_with_image_url()` / `generate_with_video_url()` 可让 `/resume/evaluate` 用图片或视频 URL / data URL 直接评价简历

## 新增一个 provider 的步骤
1. 新建 `app/llm/<name>.py`，写一个继承 `LLMProvider` 的类，实现 `generate()`
2. 在 [base.py](base.py) 的 `get_provider()` 加分支
3. `.env` 设 `LLM_PROVIDER=<name>` 及所需 key
