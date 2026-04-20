from sqlalchemy import String, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class PricingRule(Base):
    __tablename__ = "pricing_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_type: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str | None] = mapped_column(String(50), nullable=True)
    credits_per_use: Mapped[int] = mapped_column(Integer, nullable=False)
    billing_unit: Mapped[str] = mapped_column(String(20), default="per_call", nullable=False)  # per_call / per_10k_chars
    allow_free_credits: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # 是否允许签到积分抵扣
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
