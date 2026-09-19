

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from chiron_service.config import get_service_settings
from chiron_service.storage.models import Base

settings = get_service_settings()

# serve check_same_thread=False per usare sqlite su piu thread in fastapi
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
