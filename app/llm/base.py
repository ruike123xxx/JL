"""LLM provider 抽象层。

换模型只需新增一个 provider 文件并在 get_provider() 注册,
业务逻辑 (pipeline) 完全不感知具体模型。
"""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """所有模型 provider 的统一接口。"""

    @abstractmethod
    def generate(self, system: str, user: str) -> str:
        """输入 system / user 提示词, 返回模型的原始文本 (期望是 JSON 字符串)。

        注意: 这里只负责拿到原始文本, JSON 的容错解析在 core/json_repair.py 做。
        """
        raise NotImplementedError

    def generate_with_image_url(self, prompt: str, image_url: str) -> str:
        """输入文本提示词和图片 URL / data URL, 返回模型原始文本。"""
        raise NotImplementedError("当前 LLM provider 不支持图片输入")

    def generate_with_video_url(self, prompt: str, video_url: str) -> str:
        """输入文本提示词和视频 URL / data URL, 返回模型原始文本。"""
        raise NotImplementedError("当前 LLM provider 不支持视频输入")


def get_provider() -> LLMProvider:
    """按配置选择 provider 实例。"""
    from app.config import settings

    name = settings.llm_provider.lower()
    if name == "mock":
        from app.llm.mock import MockProvider

        return MockProvider()
    if name == "tongyi":
        from app.llm.tongyi import TongyiProvider

        return TongyiProvider()
    if name == "aliyun":
        from app.llm.aliyun import AliyunProvider

        return AliyunProvider()
    raise ValueError(
        f"未知的 LLM_PROVIDER: {settings.llm_provider!r} (可选: mock / tongyi / aliyun)"
    )
