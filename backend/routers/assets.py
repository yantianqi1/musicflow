from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.models.user import User
from backend.models.generation import Generation, GenerationStatus
from backend.models.voice import Voice
from backend.schemas.assets import (
    AssetItem, AssetListResponse,
    UserVoiceItem, UserVoiceListResponse,
    AssetStats,
)

router = APIRouter(prefix="/api/assets", tags=["资产"])

CATEGORY_MAP = {
    "music": ["music", "music_cover"],
    "speech": ["speech_sync", "speech_async"],
    "lyrics": ["lyrics"],
    "voice": ["voice_clone", "voice_design"],
}


def _extract_asset_item(gen: Generation) -> AssetItem:
    """Build an AssetItem from a Generation row, extracting derived fields."""
    extra = gen.extra_info or {}
    params = gen.params or {}
    return AssetItem(
        id=gen.id,
        service_type=gen.service_type,
        title=gen.title,
        model=gen.model,
        result_url=gen.result_url,
        credits_cost=gen.credits_cost,
        status=gen.status.value if hasattr(gen.status, "value") else str(gen.status),
        created_at=gen.created_at.isoformat(),
        duration_ms=extra.get("duration_ms") or extra.get("audio_length"),
        lyrics_text=extra.get("lyrics"),
        voice_id=extra.get("voice_id"),
    )


@router.get("/generations", response_model=AssetListResponse)
async def list_generations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = select(Generation).where(
        Generation.user_id == user.id,
        Generation.status == GenerationStatus.success,
    )
    if category and category in CATEGORY_MAP:
        base = base.where(Generation.service_type.in_(CATEGORY_MAP[category]))

    # Total count
    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginated results
    rows = (await db.execute(
        base.order_by(Generation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()

    return AssetListResponse(
        items=[_extract_asset_item(g) for g in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/voices", response_model=UserVoiceListResponse)
async def list_user_voices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = select(Voice).where(Voice.user_id == user.id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(Voice.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()

    return UserVoiceListResponse(
        items=[
            UserVoiceItem(
                id=v.id,
                voice_id=v.voice_id,
                voice_type=v.voice_type,
                name=v.name,
                description=v.description,
                created_at=v.created_at.isoformat(),
            )
            for v in rows
        ],
        total=total,
    )


@router.get("/stats", response_model=AssetStats)
async def get_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = select(Generation).where(
        Generation.user_id == user.id,
        Generation.status == GenerationStatus.success,
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    async def _count(types: list[str]) -> int:
        q = base.where(Generation.service_type.in_(types))
        return (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0

    music_count = await _count(["music", "music_cover"])
    speech_count = await _count(["speech_sync", "speech_async"])
    lyrics_count = await _count(["lyrics"])
    voice_count = await _count(["voice_clone", "voice_design"])

    credits_q = select(func.coalesce(func.sum(Generation.credits_cost), 0)).where(
        Generation.user_id == user.id,
        Generation.status == GenerationStatus.success,
    )
    total_credits = (await db.execute(credits_q)).scalar() or 0

    return AssetStats(
        total_generations=total,
        music_count=music_count,
        speech_count=speech_count,
        lyrics_count=lyrics_count,
        voice_count=voice_count,
        total_credits_spent=total_credits,
    )
