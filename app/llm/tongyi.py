"""通义 (Qwen) provider 骨架。

通义/豆包/DeepSeek 大多兼容 OpenAI Chat Completions 格式, 这里用 httpx 直接
打兼容接口, 不强依赖某家 SDK。换 DeepSeek/豆包时只需改 .env 里的
LLM_BASE_URL / LLM_MODEL / LLM_API_KEY, 通常无需改代码。

本次为骨架: 默认 provider 是 mock, 这里填好真实调用结构, 接 key 即可启用。
"""
import httpx

from app.config import settings
from app.llm.base import LLMProvider


class TongyiProvider(LLMProvider):
    def generate(self, system: str, user: str) -> str:
        if not settings.llm_api_key:
            raise RuntimeError(
                "LLM_PROVIDER=tongyi 但未配置 LLM_API_KEY, 请在 .env 中填写。"
            )

        url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.7,
            # 兼容接口通常支持强制 JSON 输出; 个别模型不支持时可注释掉此行
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }

        resp = httpx.post(url, json=payload, headers=headers, timeout=60.0)
        resp.raise_for_status()
        data = resp.json()
        # OpenAI 兼容格式: choices[0].message.content
        return data["choices"][0]["message"]["content"]
