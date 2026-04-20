from pydantic import BaseModel


class AssetItem(BaseModel):
    id: str
    service_type: str
    title: str | None = None
    model: str | None = None
    result_url: str | None = None
    credits_cost: int = 0
    status: str = "success"
    created_at: str
    # Derived fields for frontend convenience
    duration_ms: int | None = None
    lyrics_text: str | None = None
    voice_id: str | None = None


class AssetListResponse(BaseModel):
    items: list[AssetItem]
    total: int
    page: int
    page_size: int


class UserVoiceItem(BaseModel):
    id: str
    voice_id: str
    voice_type: str
    name: str | None = None
    description: str | None = None
    created_at: str


class UserVoiceListResponse(BaseModel):
    items: list[UserVoiceItem]
    total: int


class AssetStats(BaseModel):
    total_generations: int
    music_count: int
    speech_count: int
    lyrics_count: int
    voice_count: int
    total_credits_spent: int
