import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # configurazione llm (gemini o openai)
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # parametri agente e sandbox
    max_iterations: int = 5
    sandbox_timeout_seconds: int = 15
    default_output_dir: str = "output/plots"


def get_settings() -> Settings:
    return Settings()
