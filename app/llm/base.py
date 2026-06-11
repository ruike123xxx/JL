"""LLM provider 抽象层。

换模型只需新增一个 provider 文件并在 get_provider() 注册,
业务逻辑 (pipeline) 完全不感知具体模型。

稳定性收口在这一层: 所有真实 HTTP provider 都走 post_with_retry(),
统一做超时 / 429 限流 / 5xx / 网络抖动的指数退避重试; 重试耗尽后抛
LLMUnavailableError, 由上层 (pipeline) 决定降级为兜底回复, 不让接口 500。
"""

import time
from abc import ABC, abstractmethod

import httpx


class LLMError(Exception):
    """模型调用相关错误基类。"""


class LLMUnavailableError(LLMError):
    """重试耗尽后模型仍不可用 (限流 / 超时 / 5xx / 网络)。

    上层应据此降级为兜底回复, 而不是把异常透传成 500。
    """


# 模块级连接池: 复用 TCP/TLS 连接, 避免每次请求重新握手。
# 同步路由下用同步 Client; provider 内部统一通过 _client() 取用。
_HTTP_CLIENT: httpx.Client | None = None


def _client(timeout: float) -> httpx.Client:
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None:
        _HTTP_CLIENT = httpx.Client(
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )
    return _HTTP_CLIENT


# 这些状态码代表"再试一次可能成功": 限流 + 服务端临时故障。
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def post_with_retry(
    url: str,
    *,
    json: dict,
    headers: dict,
    timeout: float,
    max_retries: int,
    backoff: float,
) -> dict:
    """带重试的 POST, 返回解析后的 JSON。

    - 429: 优先按响应头 Retry-After 等待, 否则指数退避。
    - 5xx / 超时 / 连接错误: 指数退避重试。
    - 4xx (除 429): 业务/鉴权错误, 不重试, 直接抛 LLMError。
    - 重试耗尽仍失败: 抛 LLMUnavailableError。
    """
    client = _client(timeout)
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            resp = client.post(url, json=json, headers=headers, timeout=timeout)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_exc = exc
            _sleep_backoff(attempt, max_retries, backoff)
            continue

        if resp.status_code in _RETRYABLE_STATUS:
            last_exc = LLMUnavailableError(
                f"模型返回可重试状态码 {resp.status_code}: {resp.text[:200]}"
            )
            if attempt < max_retries:
                _sleep_retryable(resp, attempt, backoff)
                continue
            break

        if resp.status_code >= 400:
            # 鉴权 / 参数等不可重试错误, 立即失败便于排查。
            raise LLMError(
                f"模型返回不可重试状态码 {resp.status_code}: {resp.text[:200]}"
            )

        return resp.json()

    raise LLMUnavailableError(
        f"模型调用重试 {max_retries} 次后仍失败: {last_exc}"
    ) from last_exc


def _sleep_backoff(attempt: int, max_retries: int, backoff: float) -> None:
    if attempt < max_retries:
        time.sleep(backoff * (2**attempt))


def _sleep_retryable(resp: httpx.Response, attempt: int, backoff: float) -> None:
    """429 优先遵循 Retry-After, 否则指数退避。"""
    retry_after = resp.headers.get("Retry-After")
    if retry_after:
        try:
            time.sleep(min(float(retry_after), 30.0))
            return
        except ValueError:
            pass
    time.sleep(backoff * (2**attempt))


class LLMProvider(ABC):
    """所有模型 provider 的统一接口。"""

    @abstractmethod
    def generate(self, system: str, user: str, *, temperature: float | None = None) -> str:
        """输入 system / user 提示词, 返回模型的原始文本 (期望是 JSON 字符串)。

        temperature 为 None 时由 provider 用默认主回复温度; 评分 / 修复等
        结构化场景应显式传入低温度。

        注意: 这里只负责拿到原始文本, JSON 的容错解析在 core/json_repair.py 做。
        重试耗尽时抛 LLMUnavailableError。
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
    if name in {"tongyi", "aliyun"}:
        from app.llm.aliyun import AliyunProvider

        return AliyunProvider()
    raise ValueError(
        f"未知的 LLM_PROVIDER: {settings.llm_provider!r} (可选: mock / aliyun; tongyi 为 aliyun 别名)"
    )
