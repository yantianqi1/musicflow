from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.models.user import User
from backend.models.generation import Generation, GenerationStatus, derive_generation_title
from backend.models.voice import Voice as VoiceModel
from backend.schemas.voice import (
    VoiceCloneRequest, VoiceCloneResponse,
    VoiceDesignRequest, VoiceDesignResponse,
    VoiceListResponse, VoiceItem,
)
from backend.services import voice_service
from backend.services.billing_service import check_and_deduct, refund_credits

router = APIRouter(prefix="/api/voice", tags=["声音"])


@router.post("/upload")
async def upload_audio(
    file: UploadFile = File(...),
    purpose: str = Form(...),
    user: User = Depends(get_current_user),
):
    content = await file.read()
    file_id = await voice_service.upload_file(content, file.filename or "audio.mp3", purpose)
    return {"file_id": file_id}


@router.post("/clone", response_model=VoiceCloneResponse)
async def clone(
    req: VoiceCloneRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cost, free_used, paid_used = await check_and_deduct(db, user, "voice_clone")
    gen = Generation(user_id=user.id, service_type="voice_clone", credits_cost=cost, params=req.model_dump(),
                     title=derive_generation_title("voice_clone", req.model_dump(), None))
    db.add(gen)
    try:
        result = await voice_service.clone_voice(
            file_id=req.file_id, voice_id=req.voice_id, text=req.text,
            model=req.model, prompt_audio_file_id=req.prompt_audio_file_id,
            prompt_text=req.prompt_text,
        )
        gen.status = GenerationStatus.success
        gen.result_url = result.get("trial_audio_url")
        voice_record = VoiceModel(user_id=user.id, voice_id=req.voice_id, voice_type="cloned", name=req.voice_id)
        db.add(voice_record)
        await db.commit()
        return VoiceCloneResponse(voice_id=result["voice_id"], trial_audio_url=result.get("trial_audio_url"), generation_id=gen.id)
    except Exception as e:
        await refund_credits(db, user, cost, "voice_clone", free_used, str(e))
        gen.status = GenerationStatus.failed
        await db.commit()
        raise


@router.post("/design", response_model=VoiceDesignResponse)
async def design(
    req: VoiceDesignRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cost, free_used, paid_used = await check_and_deduct(db, user, "voice_design")
    gen = Generation(user_id=user.id, service_type="voice_design", credits_cost=cost, params=req.model_dump(),
                     title=derive_generation_title("voice_design", req.model_dump(), None))
    db.add(gen)
    try:
        result = await voice_service.design_voice(req.prompt, req.preview_text, req.voice_id, aigc_watermark=req.aigc_watermark)
        gen.status = GenerationStatus.success
        gen.result_url = result.get("trial_audio_url")
        voice_record = VoiceModel(user_id=user.id, voice_id=result["voice_id"], voice_type="designed", description=req.prompt)
        db.add(voice_record)
        await db.commit()
        return VoiceDesignResponse(voice_id=result["voice_id"], trial_audio_url=result.get("trial_audio_url"), generation_id=gen.id)
    except Exception as e:
        await refund_credits(db, user, cost, "voice_design", free_used, str(e))
        gen.status = GenerationStatus.failed
        await db.commit()
        raise


@router.get("/list", response_model=VoiceListResponse)
async def get_voices(
    voice_type: str = "all",
    user: User = Depends(get_current_user),
):
    result = await voice_service.list_voices(voice_type)
    return VoiceListResponse(voices=[VoiceItem(**v) for v in result["voices"]])


@router.delete("/{voice_id}")
async def remove_voice(
    voice_id: str,
    user: User = Depends(get_current_user),
):
    await voice_service.delete_voice(voice_id)
    return {"success": True}
