from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.models.user import User
from backend.models.generation import Generation, GenerationStatus, derive_generation_title
from backend.schemas.music import (
    LyricsRequest, LyricsResponse,
    MusicGenerateRequest, MusicResponse,
    CoverRequest,
)
from backend.services import music_service
from backend.services.billing_service import check_and_deduct, refund_credits

router = APIRouter(prefix="/api/music", tags=["音乐"])


@router.post("/lyrics", response_model=LyricsResponse)
async def create_lyrics(
    req: LyricsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cost, free_used, paid_used = await check_and_deduct(db, user, "lyrics")
    gen = Generation(user_id=user.id, service_type="lyrics", credits_cost=cost, params=req.model_dump())
    db.add(gen)
    try:
        result = await music_service.generate_lyrics(req.prompt, req.mode, req.lyrics, req.title)
        gen.status = GenerationStatus.success
        gen.extra_info = result
        gen.title = derive_generation_title("lyrics", req.model_dump(), result)
        await db.commit()
        return LyricsResponse(**result)
    except Exception as e:
        await refund_credits(db, user, cost, "lyrics", free_used, str(e))
        gen.status = GenerationStatus.failed
        await db.commit()
        raise


@router.post("/generate", response_model=MusicResponse)
async def create_music(
    req: MusicGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cost, free_used, paid_used = await check_and_deduct(db, user, "music", req.model)
    gen = Generation(user_id=user.id, service_type="music", model=req.model, credits_cost=cost, params=req.model_dump(),
                     title=derive_generation_title("music", req.model_dump(), None))
    db.add(gen)
    try:
        result = await music_service.generate_music(
            model=req.model, prompt=req.prompt, lyrics=req.lyrics,
            sample_rate=req.audio_setting.sample_rate, bitrate=req.audio_setting.bitrate,
            audio_format=req.audio_setting.format,
            is_instrumental=req.is_instrumental, lyrics_optimizer=req.lyrics_optimizer,
            aigc_watermark=req.aigc_watermark, stream=req.stream,
        )
        gen.status = GenerationStatus.success
        gen.result_url = result["audio_url"]
        gen.extra_info = result
        await db.commit()
        return MusicResponse(audio_url=result["audio_url"], duration_ms=result.get("duration_ms"), file_size=result.get("file_size"), generation_id=gen.id)
    except Exception as e:
        await refund_credits(db, user, cost, "music", free_used, str(e))
        gen.status = GenerationStatus.failed
        await db.commit()
        raise


@router.post("/cover", response_model=MusicResponse)
async def create_cover(
    req: CoverRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cost, free_used, paid_used = await check_and_deduct(db, user, "music_cover", req.model)
    gen = Generation(user_id=user.id, service_type="music_cover", model=req.model, credits_cost=cost, params=req.model_dump(),
                     title=derive_generation_title("music_cover", req.model_dump(), None))
    db.add(gen)
    try:
        result = await music_service.generate_cover(
            model=req.model, prompt=req.prompt,
            audio_url=req.audio_url, audio_base64=req.audio_base64,
            lyrics=req.lyrics,
            sample_rate=req.audio_setting.sample_rate, bitrate=req.audio_setting.bitrate,
            audio_format=req.audio_setting.format,
            aigc_watermark=req.aigc_watermark,
        )
        gen.status = GenerationStatus.success
        gen.result_url = result["audio_url"]
        gen.extra_info = result
        await db.commit()
        return MusicResponse(audio_url=result["audio_url"], duration_ms=result.get("duration_ms"), file_size=result.get("file_size"), generation_id=gen.id)
    except Exception as e:
        await refund_credits(db, user, cost, "music_cover", free_used, str(e))
        gen.status = GenerationStatus.failed
        await db.commit()
        raise
