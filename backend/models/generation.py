import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, JSON, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base
import enum


class GenerationStatus(str, enum.Enum):
    pending = "pending"
    success = "success"
    failed = "failed"


class Generation(Base):
    __tablename__ = "generations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    service_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    model: Mapped[str | None] = mapped_column(String(50), nullable=True)
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    credits_cost: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(SAEnum(GenerationStatus), default=GenerationStatus.pending, nullable=False)
    extra_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


def derive_generation_title(service_type: str, params: dict | None, extra_info: dict | None) -> str:
    """Derive a user-friendly title from generation metadata."""
    params = params or {}
    extra_info = extra_info or {}
    if service_type == "lyrics":
        return extra_info.get("song_title") or params.get("title") or (params.get("prompt", "")[:50]) or "歌词"
    if service_type in ("music", "music_cover"):
        return (params.get("prompt", "")[:50]) or ("翻唱" if service_type == "music_cover" else "音乐")
    if service_type in ("speech_sync", "speech_async"):
        return (params.get("text", "")[:50]) or "语音合成"
    if service_type == "voice_clone":
        return "克隆音色: " + params.get("voice_id", "unknown")
    if service_type == "voice_design":
        return "设计音色: " + (params.get("prompt", "")[:40] or "unknown")
    return service_type
