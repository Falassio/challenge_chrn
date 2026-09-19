

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SessionModel(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="New Analysis Session")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # relazioni
    messages: Mapped[List["MessageModel"]] = relationship(
        "MessageModel", back_populates="session", cascade="all, delete-orphan", order_by="MessageModel.created_at"
    )
    artifacts: Mapped[List["ArtifactModel"]] = relationship(
        "ArtifactModel", back_populates="session", cascade="all, delete-orphan", order_by="ArtifactModel.created_at"
    )
    traces: Mapped[List["TraceStepModel"]] = relationship(
        "TraceStepModel", back_populates="session", cascade="all, delete-orphan", order_by="TraceStepModel.id"
    )


class MessageModel(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(32))  # 'user' oppure 'assistant'
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    session: Mapped["SessionModel"] = relationship("SessionModel", back_populates="messages")


class TraceStepModel(Base):
    __tablename__ = "trace_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("sessions.id"), index=True)
    step_number: Mapped[int] = mapped_column(Integer)
    thought: Mapped[str] = mapped_column(Text)
    action_type: Mapped[str] = mapped_column(String(64))
    action_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    observation_stdout: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    observation_stderr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    observation_exit_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    observation_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    plot_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    execution_time_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    session: Mapped["SessionModel"] = relationship("SessionModel", back_populates="traces")


class ArtifactModel(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("sessions.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(512))
    artifact_type: Mapped[str] = mapped_column(String(64), default="plotly_html")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    session: Mapped["SessionModel"] = relationship("SessionModel", back_populates="artifacts")
