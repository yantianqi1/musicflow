from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.middleware.auth import require_admin
from backend.models.user import User
from backend.models.transaction import Transaction, TransactionType
from backend.models.generation import Generation
from backend.models.pricing import PricingRule
from backend.schemas.admin import (
    AdminUserItem, AdminUserListResponse,
    AdjustCreditsRequest, UpdateUserStatusRequest,
    PricingRuleItem, UpdatePricingRequest,
    PlatformStats,
)
from backend.services.billing_service import admin_grant_credits

router = APIRouter(prefix="/api/admin", tags=["管理后台"])


@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    base = select(User)
    if search:
        base = base.where(User.email.contains(search) | User.username.contains(search))

    count_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = count_result.scalar() or 0

    result = await db.execute(
        base.order_by(desc(User.created_at)).offset((page - 1) * page_size).limit(page_size)
    )
    items = [
        AdminUserItem(
            id=u.id, email=u.email, username=u.username, role=u.role,
            credits=u.credits, is_active=u.is_active, created_at=u.created_at.isoformat(),
        )
        for u in result.scalars().all()
    ]
    return AdminUserListResponse(items=items, total=total, page=page, page_size=page_size)


@router.put("/users/{user_id}/credits")
async def adjust_credits(
    user_id: str,
    req: AdjustCreditsRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    await admin_grant_credits(db, target, req.amount, req.description or f"管理员 {admin.username} 调整")
    return {"credits": target.credits}


@router.put("/users/{user_id}/status")
async def update_status(
    user_id: str,
    req: UpdateUserStatusRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    target.is_active = req.is_active
    await db.commit()
    return {"is_active": target.is_active}


@router.get("/stats", response_model=PlatformStats)
async def get_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    active_users = (await db.execute(select(func.count()).select_from(select(User).where(User.is_active == True).subquery()))).scalar() or 0
    total_gens = (await db.execute(select(func.count()).select_from(Generation))).scalar() or 0

    consumed = (await db.execute(
        select(func.coalesce(func.sum(func.abs(Transaction.amount)), 0))
        .where(Transaction.type == TransactionType.consume)
    )).scalar() or 0

    recharged = (await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(Transaction.type == TransactionType.recharge)
    )).scalar() or 0

    return PlatformStats(
        total_users=total_users, active_users=active_users,
        total_generations=total_gens, total_credits_consumed=consumed,
        total_credits_recharged=recharged,
    )


@router.get("/transactions")
async def admin_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    base = select(Transaction)
    count_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = count_result.scalar() or 0
    result = await db.execute(
        base.order_by(desc(Transaction.created_at)).offset((page - 1) * page_size).limit(page_size)
    )
    items = [
        {
            "id": t.id, "user_id": t.user_id, "type": t.type, "amount": t.amount,
            "balance_after": t.balance_after, "service_type": t.service_type,
            "description": t.description, "created_at": t.created_at.isoformat(),
        }
        for t in result.scalars().all()
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/pricing", response_model=list[PricingRuleItem])
async def get_pricing(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PricingRule))
    return [
        PricingRuleItem(id=r.id, service_type=r.service_type, model=r.model, credits_per_use=r.credits_per_use, billing_unit=r.billing_unit, description=r.description)
        for r in result.scalars().all()
    ]


@router.put("/pricing/{rule_id}", response_model=PricingRuleItem)
async def update_pricing(
    rule_id: int,
    req: UpdatePricingRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PricingRule).where(PricingRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="计费规则不存在")
    rule.credits_per_use = req.credits_per_use
    if req.description is not None:
        rule.description = req.description
    await db.commit()
    return PricingRuleItem(id=rule.id, service_type=rule.service_type, model=rule.model, credits_per_use=rule.credits_per_use, billing_unit=rule.billing_unit, description=rule.description)


@router.get("/config/checkin-reward")
async def get_checkin_reward(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from backend.models.config import SystemConfig
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == "daily_checkin_reward"))
    config = result.scalar_one_or_none()
    return {"daily_checkin_reward": int(config.value) if config else 10}


@router.put("/config/checkin-reward")
async def set_checkin_reward(
    amount: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from backend.models.config import SystemConfig
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == "daily_checkin_reward"))
    config = result.scalar_one_or_none()
    if config:
        config.value = str(amount)
    else:
        db.add(SystemConfig(key="daily_checkin_reward", value=str(amount), description="每日签到奖励积分"))
    await db.commit()
    return {"daily_checkin_reward": amount}
