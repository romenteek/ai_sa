from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="AI System Analyst MVP", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/ai_sa",
        alias="DATABASE_URL",
    )
    storage_dir: Path = Field(default=Path("./storage"), alias="STORAGE_DIR")
    max_chunk_size: int = Field(default=1200, alias="MAX_CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, alias="CHUNK_OVERLAP")
    jira_export_enabled: bool = Field(default=False, alias="JIRA_EXPORT_ENABLED")
    jira_base_url: str | None = Field(default=None, alias="JIRA_BASE_URL")
    jira_user_email: str | None = Field(default=None, alias="JIRA_USER_EMAIL")
    jira_api_token: str | None = Field(default=None, alias="JIRA_API_TOKEN")
    jira_project_key: str = Field(default="AISA", alias="JIRA_PROJECT_KEY")
    jira_issue_type: str = Field(default="Task", alias="JIRA_ISSUE_TYPE")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    return settings
