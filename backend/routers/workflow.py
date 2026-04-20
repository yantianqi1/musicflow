from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.models.user import User
from backend.models.generation import Generation, GenerationStatus
from backend.services import music_service
from backend.services.billing_service import check_and_deduct, refund_credits

router = APIRouter(prefix="/api/workflow", tags=["工作流"])


class LyricsToSongRequest(BaseModel):
    theme: str
    style_hint: str = ""
    model: str = "music-2.6"
    sample_rate: int = 44100
    bitrate: int = 256000
    audio_format: str = "mp3"


class LyricsToSongResponse(BaseModel):
    song_title: str
    style_tags: str
    lyrics: str
    audio_url: str
    duration_ms: Optional[int] = None
    lyrics_generation_id: str
    music_generation_id: str


@router.post("/lyrics-to-song", response_model=LyricsToSongResponse)
async def lyrics_to_song(
    req: LyricsToSongRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Step 1: 歌词生成
    lyrics_cost, lyrics_free, lyrics_paid = await check_and_deduct(db, user, "lyrics")
    lyrics_gen = Generation(user_id=user.id, service_type="lyrics", credits_cost=lyrics_cost)
    db.add(lyrics_gen)
    try:
        prompt = req.theme
        if req.style_hint:
            prompt += f"，{req.style_hint}"
        lyrics_result = await music_service.generate_lyrics(prompt)
        lyrics_gen.status = GenerationStatus.success
        lyrics_gen.extra_info = lyrics_result
    except Exception as e:
        await refund_credits(db, user, lyrics_cost, "lyrics", lyrics_free, str(e))
        lyrics_gen.status = GenerationStatus.failed
        await db.commit()
        raise

    # Step 2: 音乐生成
    music_cost, music_free, music_paid = await check_and_deduct(db, user, "music", req.model)
    music_gen = Generation(user_id=user.id, service_type="music", model=req.model, credits_cost=music_cost)
    db.add(music_gen)
    try:
        music_result = await music_service.generate_music(
            model=req.model,
            prompt=lyrics_result["style_tags"],
            lyrics=lyrics_result["lyrics"],
            sample_rate=req.sample_rate,
            bitrate=req.bitrate,
            audio_format=req.audio_format,
        )
        music_gen.status = GenerationStatus.success
        music_gen.result_url = music_result["audio_url"]
        await db.commit()
        return LyricsToSongResponse(
            song_title=lyrics_result["song_title"],
            style_tags=lyrics_result["style_tags"],
            lyrics=lyrics_result["lyrics"],
            audio_url=music_result["audio_url"],
            duration_ms=music_result.get("duration_ms"),
            lyrics_generation_id=lyrics_gen.id,
            music_generation_id=music_gen.id,
        )
    except Exception as e:
        await refund_credits(db, user, music_cost, "music", music_free, str(e))
        music_gen.status = GenerationStatus.failed
        await db.commit()
        raise
