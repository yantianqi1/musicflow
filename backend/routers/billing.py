from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.models.user import User
from backend.models.transaction import Transaction
from backend.schemas.billing import BalanceResponse, TransactionListResponse, TransactionItem, RechargeRequest
from backend.services.billing_service import recharge_credits

router = APIRouter(prefix="/api/billing", tags=["计费"])


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(user: User = Depends(get_current_user)):
    return BalanceResponse(credits=user.credits)


@router.get("/transactions", response_model=TransactionListResponse)
async def get_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base_query = select(Transaction).where(Transaction.user_id == user.id)
    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar() or 0

    result = await db.execute(
        base_query.order_by(desc(Transaction.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        TransactionItem(
            id=t.id, type=t.type, amount=t.amount, balance_after=t.balance_after,
            service_type=t.service_type, model=t.model, description=t.description,
            created_at=t.created_at.isoformat(),
        )
        for t in result.scalars().all()
    ]
    return TransactionListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/recharge")
async def do_recharge(
    req: RechargeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 简化版充值（实际商用需接入支付系统）
    await recharge_credits(db, user, req.amount)
    return {"credits": user.credits}
