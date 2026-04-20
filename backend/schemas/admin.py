from pydantic import BaseModel
from typing import Optional


class AdminUserItem(BaseModel):
    id: str
    email: str
    username: str
    role: str
    credits: int
    is_active: bool
    created_at: str


class AdminUserListResponse(BaseModel):
    items: list[AdminUserItem]
    total: int
    page: int
    page_size: int


class AdjustCreditsRequest(BaseModel):
    amount: int
    description: str = ""


class UpdateUserStatusRequest(BaseModel):
    is_active: bool


class PricingRuleItem(BaseModel):
    id: int
    service_type: str
    model: Optional[str] = None
    credits_per_use: int
    billing_unit: str = "per_call"
    description: Optional[str] = None


class UpdatePricingRequest(BaseModel):
    credits_per_use: int
    description: Optional[str] = None


class PlatformStats(BaseModel):
    total_users: int
    active_users: int
    total_generations: int
    total_credits_consumed: int
    total_credits_recharged: int
