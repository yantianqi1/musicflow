from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.models.user import User
from backend.models.checkin import CheckIn
from backend.models.config import SystemConfig
from backend.models.transaction import Transaction, TransactionType

router = APIRouter(prefix="/api/checkin", tags=["签到"])

DEFAULT_CHECKIN_REWARD = 10  # 默认每日签到积分


async def get_checkin_reward(db: AsyncSession) -> int:
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == "daily_checkin_reward"))
    config = result.scalar_one_or_none()
    if config:
        return int(config.value)
    return DEFAULT_CHECKIN_REWARD


@router.post("/daily")
async def daily_checkin(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    existing = await db.execute(
        select(CheckIn).where(CheckIn.user_id == user.id, CheckIn.date == today)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="今日已签到")

    reward = await get_checkin_reward(db)
    user.free_credits += reward

    checkin = CheckIn(user_id=user.id, date=today, credits_earned=reward)
    db.add(checkin)

    tx = Transaction(
        user_id=user.id,
        type=TransactionType.admin_grant,
        amount=reward,
        balance_after=user.credits,
        service_type="checkin",
        description=f"每日签到 +{reward} 签到积分",
    )
    db.add(tx)
    await db.commit()

    return {
        "message": f"签到成功！获得 {reward} 签到积分",
        "free_credits": user.free_credits,
        "credits": user.credits,
        "reward": reward,
    }


@router.get("/status")
async def checkin_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    existing = await db.execute(
        select(CheckIn).where(CheckIn.user_id == user.id, CheckIn.date == today)
    )
    checked_in = existing.scalar_one_or_none() is not None

    # 连续签到天数
    streak = 0
    check_date = today
    while True:
        result = await db.execute(
            select(CheckIn).where(CheckIn.user_id == user.id, CheckIn.date == check_date)
        )
        if result.scalar_one_or_none():
            streak += 1
            check_date = date.fromordinal(check_date.toordinal() - 1)
        else:
            break

    # 本月签到次数
    month_start = today.replace(day=1)
    month_count = (await db.execute(
        select(func.count()).select_from(
            select(CheckIn).where(CheckIn.user_id == user.id, CheckIn.date >= month_start).subquery()
        )
    )).scalar() or 0

    reward = await get_checkin_reward(db)

    return {
        "checked_in_today": checked_in,
        "streak": streak,
        "month_count": month_count,
        "daily_reward": reward,
        "free_credits": user.free_credits,
    }
