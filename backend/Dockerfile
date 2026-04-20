FROM python:3.12-slim

WORKDIR /app

# 基础依赖 (curl 用于 healthcheck, build-essential 给 bcrypt/cryptography)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl build-essential \
    && rm -rf /var/lib/apt/lists/*

# 先装依赖，利用 Docker 层缓存
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# 拷贝后端源码
COPY backend/ ./backend/

# 数据 + 输出目录 (docker-compose 会挂载 volume 进来)
RUN mkdir -p ./data ./output

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 3433

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:3433/api/health || exit 1

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "3433"]
