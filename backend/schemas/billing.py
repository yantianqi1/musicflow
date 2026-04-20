from pydantic import BaseModel
from typing import Optional


class BalanceResponse(BaseModel):
    credits: int


class TransactionItem(BaseModel):
    id: str
    type: str
    amount: int
    balance_after: int
    service_type: Optional[str] = None
    model: Optional[str] = None
    description: Optional[str] = None
    created_at: str


class TransactionListResponse(BaseModel):
    items: list[TransactionItem]
    total: int
    page: int
    page_size: int


class RechargeRequest(BaseModel):
    amount: int  # 充值积分数
