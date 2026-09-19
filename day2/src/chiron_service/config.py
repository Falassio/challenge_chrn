from pathlib import Path
import os
import sys
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# aggiungo day1/src al path per importare chiron_core
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DAY1_SRC = PROJECT_ROOT / "day1" / "src"
if str(DAY1_SRC) not in sys.path:
    sys.path.insert(0, str(DAY1_SRC))

from chiron_core.config import Settings as CoreSettings, get_settings as get_core_settings


class ServiceSettings(BaseSettings):
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    host: str = Field(default="0.0.0.0", description="Host to bind service")
    port: int = Field(default=8000, description="Port to bind service")
    database_url: str = Field(
        default="sqlite:///./chiron_sessions.db",
        description="Database connection string (SQLite by default, easily swappable for Postgres)"
    )
    data_dir: str = Field(default="day1/data", description="Directory where datasets reside")
    output_dir: str = Field(default="output/plots", description="Directory where plots are stored")


def get_service_settings() -> ServiceSettings:
    return ServiceSettings()
