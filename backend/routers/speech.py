from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.models.user import User
from backend.models.generation import Generation, GenerationStatus, derive_generation_title
from backend.schemas.speech import (
    SyncSpeechRequest, SyncSpeechResponse,
    AsyncSpeechRequest, AsyncSpeechResponse,
    TaskStatusResponse,
)
from backend.services import speech_service
from backend.services.billing_service import check_and_deduct, refund_credits, estimate_cost

router = APIRouter(prefix="/api/speech", tags=["语音合成"])


@router.post("/sync", response_model=SyncSpeechResponse)
async def sync_synthesize(
    req: SyncSpeechRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cost, free_used, paid_used = await check_and_deduct(db, user, "speech_sync", req.model, char_count=len(req.text))
    gen = Generation(user_id=user.id, service_type="speech_sync", model=req.model, credits_cost=cost, params=req.model_dump(),
                     title=derive_generation_title("speech_sync", req.model_dump(), None))
    db.add(gen)
    try:
        result = await speech_service.sync_speech(
            model=req.model, text=req.text,
            voice_id=req.voice_setting.voice_id, speed=req.voice_setting.speed,
            vol=req.voice_setting.vol, pitch=req.voice_setting.pitch,
            emotion=req.voice_setting.emotion,
            sample_rate=req.audio_setting.sample_rate, bitrate=req.audio_setting.bitrate,
            audio_format=req.audio_setting.format, channel=req.audio_setting.channel,
            language_boost=req.language_boost,
            aigc_watermark=req.aigc_watermark, subtitle_enable=req.subtitle_enable,
            text_normalization=req.text_normalization, latex_read=req.latex_read,
            force_cbr=req.audio_setting.force_cbr,
        )
        gen.status = GenerationStatus.success
        gen.result_url = result["audio_url"]
        await db.commit()
        return SyncSpeechResponse(
            audio_url=result["audio_url"], duration_ms=result.get("duration_ms"),
            generation_id=gen.id, subtitle_info=result.get("subtitles"),
        )
    except Exception as e:
        await refund_credits(db, user, cost, "speech_sync", free_used, str(e))
        gen.status = GenerationStatus.failed
        await db.commit()
        raise


@router.post("/async", response_model=AsyncSpeechResponse)
async def async_synthesize(
    req: AsyncSpeechRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cost, free_used, paid_used = await check_and_deduct(db, user, "speech_async", req.model, char_count=len(req.text or ""))
    gen = Generation(user_id=user.id, service_type="speech_async", model=req.model, credits_cost=cost, params=req.model_dump(),
                     title=derive_generation_title("speech_async", req.model_dump(), None))
    db.add(gen)
    try:
        result = await speech_service.async_speech(
            model=req.model, text=req.text,
            voice_id=req.voice_setting.voice_id, speed=req.voice_setting.speed,
            vol=req.voice_setting.vol, pitch=req.voice_setting.pitch,
            emotion=req.voice_setting.emotion,
            sample_rate=req.audio_setting.sample_rate, bitrate=req.audio_setting.bitrate,
            audio_format=req.audio_setting.format, channel=req.audio_setting.channel,
            language_boost=req.language_boost,
            text_file_id=req.text_file_id,
        )
        gen.status = GenerationStatus.success
        gen.extra_info = result
        await db.commit()
        return AsyncSpeechResponse(task_id=result["task_id"], generation_id=gen.id)
    except Exception as e:
        await refund_credits(db, user, cost, "speech_async", free_used, str(e))
        gen.status = GenerationStatus.failed
        await db.commit()
        raise


@router.get("/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    user: User = Depends(get_current_user),
):
    result = await speech_service.query_task_status(task_id)
    return TaskStatusResponse(**result)


@router.get("/estimate")
async def estimate_speech_cost(
    model: str = "speech-2.8-hd",
    char_count: int = 0,
    service: str = "speech_sync",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """预估语音合成消耗积分（不扣费）。"""
    cost = await estimate_cost(db, service, model, char_count)
    return {"credits": cost, "char_count": char_count, "model": model}
