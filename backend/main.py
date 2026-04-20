from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from backend.config import OUTPUT_DIR, ADMIN_EMAIL, ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_RESET_ON_START
from backend.database import init_db, async_session, engine
from backend.models import User, UserRole, PricingRule
from backend.models.generation import derive_generation_title
from backend.utils.security import hash_password

from backend.routers import auth, music, speech, voice, workflow, billing, admin, checkin, agent, assets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)


# (service_type, model, credits, billing_unit, allow_free_credits, description)
# 1积分 = 0.01元，所有价格 = MiniMax成本 × 1.4（40%利润）
DEFAULT_PRICING = [
    # 音乐 — 按次计费
    ("lyrics", None, 7, "per_call", True, "歌词生成 (成本0.05元, 售价0.07元)"),
    ("music", "music-2.6", 140, "per_call", False, "音乐生成 Music-2.6 (成本1元/首, 售价1.4元)"),
    ("music_cover", "music-cover", 140, "per_call", False, "翻唱 Music-Cover (成本1元/首, 售价1.4元)"),
    # 语音合成 — 按万字符计费
    ("speech_sync", "speech-2.8-hd", 490, "per_10k_chars", False, "同步语音 2.8-HD (成本3.5元/万字符, 售价4.9元)"),
    ("speech_sync", "speech-2.8-turbo", 280, "per_10k_chars", False, "同步语音 2.8-Turbo (成本2元/万字符, 售价2.8元)"),
    ("speech_async", "speech-2.8-hd", 490, "per_10k_chars", False, "异步语音 2.8-HD (成本3.5元/万字符, 售价4.9元)"),
    ("speech_async", "speech-2.8-turbo", 280, "per_10k_chars", False, "异步语音 2.8-Turbo (成本2元/万字符, 售价2.8元)"),
    # 声音 — 按次计费
    ("voice_clone", None, 1386, "per_call", False, "声音克隆 (成本9.9元/音色, 售价13.86元)"),
    ("voice_design", None, 1386, "per_call", False, "声音设计 (成本9.9元/音色, 售价13.86元)"),
]


async def seed_data():
    async with async_session() as db:
        # 初始管理员 — 从 .env 读取
        result = await db.execute(select(User).where(User.email == ADMIN_EMAIL))
        existing_admin = result.scalar_one_or_none()
        if existing_admin is None:
            db.add(User(
                email=ADMIN_EMAIL,
                username=ADMIN_USERNAME,
                password_hash=hash_password(ADMIN_PASSWORD),
                role=UserRole.admin,
                credits=999999,
                is_active=True,
            ))
            logging.info("Seed: created admin user %s", ADMIN_EMAIL)
        elif ADMIN_RESET_ON_START:
            existing_admin.username = ADMIN_USERNAME
            existing_admin.password_hash = hash_password(ADMIN_PASSWORD)
            existing_admin.role = UserRole.admin
            existing_admin.is_active = True
            logging.info("Seed: ADMIN_RESET_ON_START=true, rotated credentials for %s", ADMIN_EMAIL)

        # 默认计费规则 — 按 (service_type, model) upsert，新增模型不用清库
        for stype, model, cost, unit, free_ok, desc in DEFAULT_PRICING:
            query = select(PricingRule).where(PricingRule.service_type == stype)
            query = query.where(PricingRule.model == model) if model else query.where(PricingRule.model.is_(None))
            existing = (await db.execute(query)).scalar_one_or_none()
            if existing is None:
                db.add(PricingRule(service_type=stype, model=model, credits_per_use=cost, billing_unit=unit, allow_free_credits=free_ok, description=desc))

        await db.commit()


async def run_migrations():
    """Run lightweight schema migrations for SQLite."""
    from sqlalchemy import text
    from backend.models.generation import Generation

    async with engine.begin() as conn:
        await conn.run_sync(User.metadata.create_all)

        # Check if 'title' column exists on generations table
        rows = await conn.execute(text("PRAGMA table_info(generations)"))
        columns = {r[1] for r in rows}
        if "title" not in columns:
            await conn.execute(text("ALTER TABLE generations ADD COLUMN title VARCHAR(200)"))
            logging.info("Migration: added 'title' column to generations table")

        session_rows = await conn.execute(text("PRAGMA table_info(agent_sessions)"))
        session_columns = {r[1] for r in session_rows}
        if "status" not in session_columns:
            await conn.execute(text("ALTER TABLE agent_sessions ADD COLUMN status VARCHAR(40) DEFAULT 'idle'"))
            logging.info("Migration: added 'status' column to agent_sessions")
        if "active_tool_call_id" not in session_columns:
            await conn.execute(text("ALTER TABLE agent_sessions ADD COLUMN active_tool_call_id VARCHAR(36)"))
            logging.info("Migration: added 'active_tool_call_id' column to agent_sessions")
        if "last_round_id" not in session_columns:
            await conn.execute(text("ALTER TABLE agent_sessions ADD COLUMN last_round_id VARCHAR(36)"))
            logging.info("Migration: added 'last_round_id' column to agent_sessions")

    # Backfill titles for existing rows
    async with async_session() as db:
        from backend.models.generation import Generation
        result = await db.execute(
            select(Generation).where(Generation.title.is_(None), Generation.status == "success")
        )
        rows = result.scalars().all()
        for gen in rows:
            gen.title = derive_generation_title(gen.service_type, gen.params, gen.extra_info)
        if rows:
            await db.commit()
            logging.info("Migration: backfilled titles for %d generations", len(rows))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_data()
    await run_migrations()
    yield


app = FastAPI(title="MusicFlow", description="全链路音乐创作平台", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/files", StaticFiles(directory=OUTPUT_DIR), name="files")

app.include_router(auth.router)
app.include_router(music.router)
app.include_router(speech.router)
app.include_router(voice.router)
app.include_router(workflow.router)
app.include_router(billing.router)
app.include_router(checkin.router)
app.include_router(admin.router)
app.include_router(agent.router)
app.include_router(assets.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
