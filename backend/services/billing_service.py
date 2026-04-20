import math
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.user import User
from backend.models.transaction import Transaction, TransactionType
from backend.models.pricing import PricingRule
from fastapi import HTTPException, status


async def get_pricing_rule(db: AsyncSession, service_type: str, model: str | None = None) -> PricingRule:
    query = select(PricingRule).where(PricingRule.service_type == service_type)
    if model:
        query = query.where(PricingRule.model == model)
    else:
        query = query.where(PricingRule.model.is_(None))
    result = await db.execute(query)
    rule = result.scalar_one_or_none()
    if not rule:
        result = await db.execute(
            select(PricingRule).where(PricingRule.service_type == service_type, PricingRule.model.is_(None))
        )
        rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"未配置 {service_type} 的计费规则")
    return rule


def calculate_cost(rule: PricingRule, char_count: int = 0) -> int:
    """根据计费单位计算实际积分消耗。"""
    if rule.billing_unit == "per_10k_chars" and char_count > 0:
        cost = math.ceil(rule.credits_per_use * char_count / 10000)
        return max(cost, 1)
    return rule.credits_per_use


async def check_and_deduct(db: AsyncSession, user: User, service_type: str, model: str | None = None, char_count: int = 0, description: str = "") -> tuple[int, int, int]:
    """
    检查余额并预扣积分。
    返回 (总消耗, 签到积分扣除量, 充值积分扣除量)。
    free 模型：优先扣签到积分 → 不够再扣充值积分。
    付费模型：只扣充值积分。
    """
    rule = await get_pricing_rule(db, service_type, model)
    cost = calculate_cost(rule, char_count)

    free_used = 0
    paid_used = 0

    if rule.allow_free_credits and user.free_credits > 0:
        # 优先从签到积分扣
        free_used = min(user.free_credits, cost)
        paid_used = cost - free_used
    else:
        paid_used = cost

    total_available = (user.free_credits if rule.allow_free_credits else 0) + user.credits
    if total_available < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"积分不足，需要 {cost} 积分，当前余额：充值 {user.credits} + 签到 {user.free_credits}",
        )

    user.free_credits -= free_used
    user.credits -= paid_used

    desc_parts = []
    if free_used > 0:
        desc_parts.append(f"签到积分-{free_used}")
    if paid_used > 0:
        desc_parts.append(f"充值积分-{paid_used}")
    deduct_desc = description or f"使用 {service_type} ({', '.join(desc_parts)})"

    tx = Transaction(
        user_id=user.id,
        type=TransactionType.consume,
        amount=-cost,
        balance_after=user.credits,
        service_type=service_type,
        model=model,
        description=deduct_desc,
    )
    db.add(tx)
    await db.flush()
    return cost, free_used, paid_used


async def estimate_cost(db: AsyncSession, service_type: str, model: str | None = None, char_count: int = 0) -> int:
    """预估消耗积分（不扣费），供前端展示。"""
    rule = await get_pricing_rule(db, service_type, model)
    return calculate_cost(rule, char_count)


async def refund_credits(db: AsyncSession, user: User, amount: int, service_type: str, free_portion: int = 0, description: str = ""):
    """生成失败时回退积分。free_portion 指需退回签到积分的部分。"""
    paid_portion = amount - free_portion
    user.free_credits += free_portion
    user.credits += paid_portion
    tx = Transaction(
        user_id=user.id,
        type=TransactionType.refund,
        amount=amount,
        balance_after=user.credits,
        service_type=service_type,
        description=description or f"{service_type} 生成失败，退还积分（签到{free_portion}+充值{paid_portion}）",
    )
    db.add(tx)
    await db.flush()


async def recharge_credits(db: AsyncSession, user: User, amount: int, description: str = ""):
    """充值积分。"""
    user.credits += amount
    tx = Transaction(
        user_id=user.id,
        type=TransactionType.recharge,
        amount=amount,
        balance_after=user.credits,
        description=description or f"充值 {amount} 积分",
    )
    db.add(tx)
    await db.commit()


async def admin_grant_credits(db: AsyncSession, user: User, amount: int, description: str = ""):
    """管理员手动调整充值积分。"""
    user.credits += amount
    tx = Transaction(
        user_id=user.id,
        type=TransactionType.admin_grant,
        amount=amount,
        balance_after=user.credits,
        description=description or f"管理员调整 {amount} 积分",
    )
    db.add(tx)
    await db.commit()
