"""User-level character→voice memory for novel dubbing.

Wraps around `voice_casting` without adding DB access there. Loaded once per
`batch_voice_over` confirmation, saved once on successful execution.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.agent_voice_memory import AgentVoiceMemory
from backend.services.voice_casting import NARRATION_ROLES

logger = logging.getLogger(__name__)

_CANONICAL_NARRATOR_KEY = "旁白"
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_role_key(role_name: str | None) -> str | None:
    """Return a canonical key for a role name, or None if empty.

    Steps: NFKC → strip → collapse whitespace → lowercase Latin letters →
    narrator aliases collapse to canonical "旁白".
    """
    if not role_name:
        return None
    text = unicodedata.normalize("NFKC", role_name).strip()
    text = _WHITESPACE_RE.sub("", text)
    if not text:
        return None
    text = "".join(ch.lower() if ch.isascii() and ch.isalpha() else ch for ch in text)
    if text in NARRATION_ROLES or "旁白" in text or "叙述" in text:
        return _CANONICAL_NARRATOR_KEY
    return text


async def load_memory_map(db: AsyncSession, user_id: str) -> dict[str, dict[str, Any]]:
    """Return {role_key: {voice_id, role_display, source, usage_count}} for a user."""
    stmt = select(AgentVoiceMemory).where(AgentVoiceMemory.user_id == user_id)
    rows = (await db.execute(stmt)).scalars().all()
    return {
        row.role_key: {
            "voice_id": row.voice_id,
            "role_display": row.role_display,
            "source": row.source,
            "usage_count": row.usage_count,
        }
        for row in rows
    }


def _voice_name_from_catalog(voices: list[dict], voice_id: str) -> str | None:
    for voice in voices:
        if voice.get("voice_id") == voice_id:
            return voice.get("voice_name") or voice_id
    return None


def _promote_candidate(role: dict, voice_id: str, voice_name: str | None) -> None:
    """Move the memorized voice to candidates[0]; prepend a fallback entry if absent."""
    candidates = list(role.get("candidates") or [])
    matched_idx = next(
        (i for i, c in enumerate(candidates) if c.get("voice_id") == voice_id),
        None,
    )
    if matched_idx is not None:
        picked = candidates.pop(matched_idx)
        candidates.insert(0, picked)
    else:
        candidates.insert(0, {
            "voice_id": voice_id,
            "voice_name": voice_name or voice_id,
            "intro": "沿用之前的音色记忆",
            "score": 999,
            "reason": "与历史配音保持一致",
        })
    role["candidates"] = candidates


async def apply_memory_to_selection(
    db: AsyncSession,
    user_id: str,
    voice_selection: dict,
    voices: list[dict],
) -> tuple[dict, dict[str, str]]:
    """Override voice_selection.roles with user-level memory where applicable.

    Returns (mutated voice_selection, memory_hits) where memory_hits maps
    role_name → voice_id for each role we overrode.
    """
    roles = list(voice_selection.get("roles") or [])
    if not roles:
        return voice_selection, {}

    memory_map = await load_memory_map(db, user_id)
    if not memory_map:
        return voice_selection, {}

    catalog_ids = {voice.get("voice_id") for voice in voices if voice.get("voice_id")}
    hits: dict[str, str] = {}

    for role in roles:
        key = normalize_role_key(role.get("role"))
        if not key or key not in memory_map:
            continue
        memory = memory_map[key]
        memorized_voice_id = memory["voice_id"]
        if catalog_ids and memorized_voice_id not in catalog_ids:
            logger.warning(
                "Voice memory for role %r references missing voice_id %s; falling back to heuristic",
                role.get("role"),
                memorized_voice_id,
            )
            continue
        role["selected_voice_id"] = memorized_voice_id
        role["from_memory"] = True
        role["memory_source"] = memory.get("source")
        voice_name = _voice_name_from_catalog(voices, memorized_voice_id)
        _promote_candidate(role, memorized_voice_id, voice_name)
        hits[role.get("role") or key] = memorized_voice_id

    voice_selection["roles"] = roles
    return voice_selection, hits


async def save_memory_from_tool_params(
    db: AsyncSession,
    user_id: str,
    tool_params: dict,
    session_id: str | None = None,
    source: str = "user",
) -> list[dict]:
    """Upsert memory from the final tool_params (post user overrides).

    Only the first non-empty voice_id per normalized role_key is kept.
    Returns serialized records that were created or updated.
    """
    segments = tool_params.get("segments") or []
    if not segments:
        return []

    # Deduplicate: later segments overwrite earlier ones so the user's final
    # override in the confirmation card (which rewrites every segment for the
    # role) is what we save — not the first segment, which may be stale.
    per_role: dict[str, tuple[str, str]] = {}  # role_key → (voice_id, role_display)
    for segment in segments:
        voice_id = (segment.get("voice_id") or "").strip()
        if not voice_id:
            continue
        role_name = segment.get("role") or ""
        key = normalize_role_key(role_name)
        if not key:
            continue
        per_role[key] = (voice_id, role_name.strip() or key)

    if not per_role:
        return []

    existing_rows = (
        await db.execute(
            select(AgentVoiceMemory)
            .where(AgentVoiceMemory.user_id == user_id)
            .where(AgentVoiceMemory.role_key.in_(per_role.keys()))
        )
    ).scalars().all()
    existing_by_key = {row.role_key: row for row in existing_rows}

    updated: list[AgentVoiceMemory] = []
    for key, (voice_id, role_display) in per_role.items():
        row = existing_by_key.get(key)
        if row is None:
            row = AgentVoiceMemory(
                user_id=user_id,
                role_key=key,
                role_display=role_display,
                voice_id=voice_id,
                source=source,
                last_session_id=session_id,
                usage_count=1,
            )
            db.add(row)
        else:
            row.voice_id = voice_id
            row.role_display = role_display
            row.source = source
            row.last_session_id = session_id
            row.usage_count = (row.usage_count or 0) + 1
        updated.append(row)

    await db.flush()
    return [_serialize(row) for row in updated]


async def list_user_memory(db: AsyncSession, user_id: str) -> list[dict]:
    stmt = (
        select(AgentVoiceMemory)
        .where(AgentVoiceMemory.user_id == user_id)
        .order_by(AgentVoiceMemory.updated_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_serialize(row) for row in rows]


async def clear_user_memory(db: AsyncSession, user_id: str) -> int:
    result = await db.execute(
        delete(AgentVoiceMemory).where(AgentVoiceMemory.user_id == user_id)
    )
    return int(result.rowcount or 0)


async def clear_role_memory(db: AsyncSession, user_id: str, role_key: str) -> int:
    key = normalize_role_key(role_key) or role_key
    result = await db.execute(
        delete(AgentVoiceMemory).where(
            AgentVoiceMemory.user_id == user_id,
            AgentVoiceMemory.role_key == key,
        )
    )
    return int(result.rowcount or 0)


def _serialize(row: AgentVoiceMemory) -> dict:
    return {
        "id": row.id,
        "role_key": row.role_key,
        "role_display": row.role_display,
        "voice_id": row.voice_id,
        "source": row.source,
        "last_session_id": row.last_session_id,
        "usage_count": row.usage_count,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
