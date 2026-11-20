from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    mysql_url: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    github_token: str = ""

@lru_cache
def get_settings() -> Settings:
    return Settings()
