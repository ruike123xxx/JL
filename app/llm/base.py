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
    raise ValueError(f"未知的 LLM_PROVIDER: {settings.llm_provider!r} (可选: mock / tongyi)")
