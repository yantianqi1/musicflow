import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import AGENT_UPLOAD_DIR
from backend.models.agent_attachment import AgentAttachment, AgentAttachmentType
from backend.models.user import User


TEXT_EXTENSIONS = {".txt", ".md", ".srt", ".lrc"}


def _detect_attachment_type(filename: str, mime_type: str) -> AgentAttachmentType:
    suffix = Path(filename).suffix.lower()
    if mime_type.startswith("audio/"):
        return AgentAttachmentType.audio
    if mime_type.startswith("image/"):
        return AgentAttachmentType.image
    if mime_type.startswith("text/") or suffix in TEXT_EXTENSIONS:
        return AgentAttachmentType.text
    return AgentAttachmentType.binary


def _extract_text(kind: AgentAttachmentType, content: bytes) -> str | None:
    if kind != AgentAttachmentType.text:
        return None
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


async def save_attachment(
    db: AsyncSession,
    user: User,
    session_id: str,
    file: UploadFile,
) -> AgentAttachment:
    content = await file.read()
    kind = _detect_attachment_type(file.filename or "file.bin", file.content_type or "application/octet-stream")
    attachment_id = str(uuid.uuid4())
    storage_name = f"{attachment_id}-{file.filename or 'upload.bin'}"
    storage_path = os.path.join(AGENT_UPLOAD_DIR, storage_name)
    with open(storage_path, "wb") as handle:
        handle.write(content)

    attachment = AgentAttachment(
        id=attachment_id,
        session_id=session_id,
        user_id=user.id,
        kind=kind,
        original_name=file.filename or "upload.bin",
        mime_type=file.content_type or "application/octet-stream",
        storage_path=storage_path,
        extracted_text=_extract_text(kind, content),
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return attachment


async def get_attachment(db: AsyncSession, attachment_id: str, user: User) -> AgentAttachment:
    result = await db.execute(
        select(AgentAttachment).where(
            AgentAttachment.id == attachment_id,
            AgentAttachment.user_id == user.id,
        )
    )
    attachment = result.scalar_one_or_none()
    if attachment is None:
        raise HTTPException(status_code=404, detail="附件不存在")
    return attachment


async def list_session_attachments(db: AsyncSession, session_id: str, user: User) -> list[AgentAttachment]:
    result = await db.execute(
        select(AgentAttachment)
        .where(AgentAttachment.session_id == session_id, AgentAttachment.user_id == user.id)
        .order_by(AgentAttachment.created_at)
    )
    return list(result.scalars().all())


async def read_attachment_bytes(db: AsyncSession, attachment_id: str, user: User) -> bytes:
    attachment = await get_attachment(db, attachment_id, user)
    with open(attachment.storage_path, "rb") as handle:
        return handle.read()


def summarize_attachments(attachments: list[AgentAttachment]) -> str:
    if not attachments:
        return "无附件"
    lines = []
    for item in attachments[:5]:
        summary = item.extracted_text[:80].replace("\n", " ") if item.extracted_text else item.original_name
        lines.append(f"- {item.kind.value}: {summary}")
    return "\n".join(lines)
