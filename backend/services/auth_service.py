from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.user import User, UserRole
from backend.utils.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from backend.schemas.auth import TokenResponse


async def register_user(db: AsyncSession, email: str, username: str, password: str) -> User:
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise ValueError("该邮箱已注册")

    user = User(
        email=email,
        username=username,
        password_hash=hash_password(password),
        role=UserRole.user,
        credits=0,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user and verify_password(password, user.password_hash):
        return user
    return None


def generate_tokens(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id),
    )


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> TokenResponse | None:
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        return None
    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        return None
    return generate_tokens(user)
