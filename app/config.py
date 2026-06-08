"""集中配置: 从环境变量 / .env 读取。"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 服务
    host: str = "127.0.0.1"
    port: int = 8000

    # 模型 provider: mock / tongyi / aliyun
    llm_provider: str = "aliyun"

    # 真实模型配置 (mock 时可留空)
    llm_api_key: str = ""
    llm_model: str = "qwen3-vl-plus"
    llm_vision_model: str = "qwen3-vl-plus"
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # 模型调用稳定性: 超时 / 重试 / 退避
    llm_timeout: float = 30.0  # 单次请求超时(秒)
    llm_max_retries: int = 2  # 可重试错误(429/5xx/超时/网络)额外重试次数
    llm_retry_backoff: float = 0.8  # 指数退避基数(秒): 第 n 次重试等待 backoff * 2**n

    # 分场景温度: 主回复保留随机度, 评分/修复要稳定
    llm_temperature_reply: float = 0.7
    llm_temperature_structured: float = 0.1  # 评分 / JSON 修复等结构化任务

    # 数据库
    db_path: str = "sessions.db"


settings = Settings()
