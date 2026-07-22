from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    mysql_url: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    redis_url: str
    openai_api_key: str
    openai_base_url: str = "https://api.openai.com/v1"

@lru_cache
def get_settings() -> Settings:
    return Settings()
