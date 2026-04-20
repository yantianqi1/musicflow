from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, RefreshRequest, UserProfile
from backend.services.auth_service import register_user, authenticate_user, generate_tokens, refresh_access_token
from backend.middleware.auth import get_current_user
from backend.models.user import User

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        user = await register_user(db, req.email, req.username, req.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return generate_tokens(user)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, req.email, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")
    return generate_tokens(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    tokens = await refresh_access_token(db, req.refresh_token)
    if not tokens:
        raise HTTPException(status_code=401, detail="无效的刷新令牌")
    return tokens


@router.get("/profile", response_model=UserProfile)
async def profile(user: User = Depends(get_current_user)):
    return UserProfile(
        id=user.id,
        email=user.email,
        username=user.username,
        role=user.role,
        credits=user.credits,
        free_credits=user.free_credits,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
    )
