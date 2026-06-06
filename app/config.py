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

    # 数据库
    db_path: str = "sessions.db"


settings = Settings()
