from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(
    f"sqlite:///{settings.sqlite_path}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
