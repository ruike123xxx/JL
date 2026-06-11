"""阿里云通义千问 provider。"""

from app.config import settings
from app.llm.base import LLMProvider, post_with_retry


class AliyunProvider(LLMProvider):
    """调用阿里云百炼 DashScope OpenAI 兼容接口。"""

    def generate(self, system: str, user: str, *, temperature: float | None = None) -> str:
        self._ensure_api_key()
        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": (
                settings.llm_temperature_reply if temperature is None else temperature
            ),
            "response_format": {"type": "json_object"},
        }
        return self._chat_completions(payload)

    def generate_with_image_url(self, prompt: str, image_url: str) -> str:
        return self._generate_with_media_url(
            prompt=prompt,
            media_url=image_url,
            media_type="image_url",
        )

    def generate_with_video_url(self, prompt: str, video_url: str) -> str:
        return self._generate_with_media_url(
            prompt=prompt,
            media_url=video_url,
            media_type="video_url",
        )

    def _generate_with_media_url(
        self, *, prompt: str, media_url: str, media_type: str
    ) -> str:
        self._ensure_api_key()
        payload = {
            "model": settings.llm_vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": media_type, media_type: {"url": media_url}},
                    ],
                }
            ],
            "temperature": 0.2,
        }
        return self._chat_completions(payload)

    def _ensure_api_key(self) -> None:
        if not settings.llm_api_key:
            raise RuntimeError(
                "LLM_PROVIDER=aliyun 但未配置 LLM_API_KEY, 请在 .env 中填写阿里云百炼 API Key。"
            )

    def _chat_completions(self, payload: dict) -> str:
        url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        data = post_with_retry(
            url,
            json=payload,
            headers=headers,
            timeout=settings.llm_timeout,
            max_retries=settings.llm_max_retries,
            backoff=settings.llm_retry_backoff,
        )
        return data["choices"][0]["message"]["content"]
