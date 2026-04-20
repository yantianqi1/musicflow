# MusicFlow · AI 全链路音乐创作平台

基于 MiniMax API 的 SaaS 平台：一个对话式 Agent 串起**歌词 / 音乐 / 翻唱 / 同步 & 异步语音 / 声音克隆 / 声音设计**全流程，带用户体系、双积分计费、管理后台和生成物管理。

- **Backend**: FastAPI + SQLAlchemy async + SQLite（可切 Postgres）
- **Frontend**: React 19 + Vite + Tailwind CSS 4 + Zustand
- **LLM**: 任意 OpenAI 兼容接口（DeepSeek / Gemini 代理 / Ollama / vLLM …）
- **Media**: MiniMax `music_generation` / `lyrics_generation` / `t2a_v2` / `t2a_async_v2` / `voice_clone` / `voice_design`

---

## 功能一览

- 💬 **Agent Workspace** — 自然语言对话驱动 13 个工具调用（写歌、合成、克隆…），支持 SSE 流式响应、敏感操作用户确认、附件上传
- 🎵 **音乐生成** — MiniMax Music-2.6，自动生成封面
- 🎤 **翻唱** — Music-Cover 换声不换曲
- ✍️ **歌词生成** — 按主题/风格生成结构化歌词
- 🔊 **语音合成** — Speech-2.8-HD / Turbo，同步接口 + 长文本异步接口
- 👤 **声音克隆 / 声音设计** — 上传样本即可生成私有 voice_id
- 💰 **双积分计费** — 付费积分 + 每日签到免费积分，调用前扣费、失败自动退款
- 🛡️ **管理后台** — 用户管理、价格规则热更新、对账流水
- 📁 **生成物库** — 所有音频 / 封面集中归档，支持搜索与下载

---

## 目录结构

```
musicflow/
├── backend/                 # FastAPI 后端
│   ├── main.py              # 入口 + 启动时初始化 admin & 价格规则
│   ├── config.py            # 环境变量加载
│   ├── database.py          # async SQLAlchemy
│   ├── routers/             # 路由层（billing 在此处 check_and_deduct / refund）
│   ├── services/            # 业务层
│   │   ├── minimax_client.py    # 唯一对外 HTTP 客户端
│   │   ├── agent_service.py     # LLM ↔ tool-calling 主循环 (SSE)
│   │   ├── agent_tools.py       # 13 个 OpenAI function tools
│   │   └── llm_client.py        # OpenAI 兼容封装
│   ├── models/              # ORM
│   ├── schemas/             # Pydantic I/O
│   └── requirements.txt
├── frontend/                # React 前端
│   ├── src/
│   │   ├── App.jsx          # react-router v7 路由
│   │   ├── pages/agent/AgentWorkspace.jsx  # Agent 主界面
│   │   ├── store/           # zustand
│   │   └── api/             # axios + token 拦截
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml       # 一键部署
├── .env.example             # 环境变量模板
└── data/ · output/          # 运行时 volume：DB & 生成音频
```

---

## 快速开始 · 本地开发

### 1. 填写 `.env`

```bash
cp .env.example .env
# 编辑 .env，至少填 MINIMAX_API_KEY / SECRET_KEY / LLM_*
```

### 2. 后端 (port 3433)

```bash
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --host 0.0.0.0 --port 3433 --reload
```

### 3. 前端 (port 3434)

```bash
cd frontend
npm install
npm run dev
```

- 前端：http://localhost:3434
- 后端：http://localhost:3433
- Vite dev 会把 `/api` 与 `/files` 代理到后端

### 4. 默认管理员

| Email | Password |
|---|---|
| `admin@musicflow.com` | `admin123` |

> 首次启动时由 `main.py::seed_data()` 自动创建，并写入一份默认价格规则。

---

## Docker 部署（推荐）

```bash
# 1. 配置环境变量
cp .env.example .env
vim .env

# 2. 一键启动
docker compose up -d --build

# 3. 查看状态
docker compose ps
docker compose logs -f backend
```

- 前端访问：`http://<server-ip>:8080`（默认端口，可用 `FRONTEND_PORT` 改）
- 后端不对外暴露，由前端容器 nginx 反代 `/api` 与 `/files`
- 数据持久化：`./data`（SQLite）和 `./output`（音频文件）以 volume 方式挂载到宿主机

### 端口自定义

```bash
FRONTEND_PORT=9000 docker compose up -d --build
```

### 升级

```bash
git pull
docker compose up -d --build
```

### 停止 / 清理

```bash
docker compose down            # 停容器，保留数据
docker compose down -v         # 连同 volume 一起删（会丢数据）
```

### 日志 & 健康检查

- 后端健康检查：`GET /api/health` → `{"status":"ok"}`
- 容器级 healthcheck 已在 Dockerfile / compose 里配置，`docker compose ps` 可见状态

---

## 环境变量

见 [`.env.example`](./.env.example)。关键项：

| 变量 | 必填 | 说明 |
|---|---|---|
| `MINIMAX_API_KEY` | ✅ | MiniMax 平台 API Key |
| `MINIMAX_BASE_URL` | | 默认 `https://api.minimaxi.com/v1` |
| `SECRET_KEY` | ✅ | JWT 签名密钥，生产请用 `openssl rand -hex 32` 生成 |
| `DATABASE_URL` | | 默认 SQLite；可切 Postgres `postgresql+asyncpg://...` |
| `LLM_BASE_URL` | ✅ | OpenAI 兼容端点 |
| `LLM_API_KEY` | ✅ | LLM Key |
| `LLM_MODEL` | ✅ | 模型名，如 `deepseek-chat` / `gpt-4o-mini` |
| `LLM_MAX_TOKENS` | | 默认 `4096` |

---

## 架构要点

### Agent 工具调用流程

```
User → /api/agent/chat (SSE)
  → agent_service.py
  → LLM.chat.completions (携带 13 个 tool schema)
  → tool_calls?
      ├─ require_confirmation=True  → 前端弹确认卡 → 用户确认
      └─ 直接执行 → executor(...) → minimax_client → 返回结果
  → billing_service.check_and_deduct() 调用前扣费
  → 失败自动 refund_credits()
```

### 计费模型

- 单位：**1 积分 = 0.01 元**，全部价格 = MiniMax 成本 × 1.4（默认 40% 毛利）
- 两种积分：**付费积分** + **免费积分**（每日签到）
- 价格规则存储在 `pricing_rules` 表，启动时按 `(service_type, model)` 维度 upsert，新增模型不用清库
- 计费单位：`per_call`（按次）或 `per_10k_chars`（按万字符）

### MiniMax 客户端

- `backend/services/minimax_client.py` 是全局单例 HTTP 客户端
- Bearer Auth、120s timeout、所有 `/v1/*` 调用走这里，便于统一加日志 / 重试 / 限流

---

## 开发

```bash
# Lint 前端
cd frontend && npm run lint

# 数据库迁移
# SQLite 场景下 main.py::run_migrations() 会做轻量 ALTER TABLE
# 切 Postgres 后建议接入 Alembic
```

---

## License

MIT
