import uuid
import enum
from datetime import datetime
from sqlalchemy import String, DateTime, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class AgentSessionStatus(str, enum.Enum):
    idle = "idle"
    awaiting_confirmation = "awaiting_confirmation"
    executing = "executing"
    awaiting_input = "awaiting_input"
    completed = "completed"
    cancelled = "cancelled"


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[AgentSessionStatus] = mapped_column(SAEnum(AgentSessionStatus), default=AgentSessionStatus.idle, nullable=False)
    active_tool_call_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_round_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.status is None:
            self.status = AgentSessionStatus.idle
