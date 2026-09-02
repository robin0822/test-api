from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Document Summary API"
    database_url: str = "sqlite:///./test-api.db"
    redis_url: str = "redis://localhost:6379/0"
    upload_dir: str = "/data/uploads"
    max_file_size: int = 20 * 1024 * 1024
    max_batch_files: int = 10
    model_api_base: str = "https://maas-api.cn-huabei-1.xf-yun.com/v2"
    model_api_key: str = ""
    model_id: str = "xopkimik26"
    model_temperature: float = 0.3
    model_max_tokens: int = 4096
    model_chunk_chars: int = 30_000
    model_mock: bool = False
    api_token: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
