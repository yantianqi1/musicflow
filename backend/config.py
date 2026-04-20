import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/musicflow.db")
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
ALGORITHM = "HS256"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
AGENT_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "agent_uploads")

# LLM (OpenAI-compatible)
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))

# Admin seed (首次启动时写入 DB 的初始管理员)
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@musicflow.com")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
# true=每次启动都把 ADMIN_EMAIL 用户的密码/用户名重置为 .env 值 (适合忘密码场景)
ADMIN_RESET_ON_START = os.getenv("ADMIN_RESET_ON_START", "false").lower() in ("1", "true", "yes")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(AGENT_UPLOAD_DIR, exist_ok=True)
