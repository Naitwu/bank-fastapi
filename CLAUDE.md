# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## CRITICAL RULE: 技術文件優先原則

**在產生任何程式碼前，必須先嚴格參考並遵循 `/docs` 目錄下的所有技術規範文件。這是最高優先級的規則。**

目前可用的技術文件：
- `/docs/email_template.md` - Email 模板生成規範（必須使用 Jinja2、台灣繁體中文用語、雙格式等）

所有程式碼生成必須：
1. 先讀取相關的技術文件
2. 完全遵循文件中的規範
3. 使用文件中指定的命名慣例、樣式規範和安全要求

## Project Overview

FastAPI-based banking application using Python 3.13. The project uses Pipenv for dependency management and is structured as a modular FastAPI application with environment-based configuration.

**技術堆疊**：
- **Framework**: FastAPI (with standard extras)
- **Database**: PostgreSQL with SQLModel (0.0.22) + Alembic (1.14.0)
- **Async DB Drivers**: asyncpg (0.30.0), psycopg[binary,pool]
- **Authentication**: Argon2-CFFI (23.1.0) for password hashing
- **Task Queue**: Celery (5.3.6) with RabbitMQ (broker) + Redis (backend)
- **Monitoring**: Flower (2.0.1), Redisbeat (1.2.6)
- **Email**: FastAPI-Mail (1.4.2), aiosmtplib (3.0.2)
- **Logging**: Loguru (0.7.3)
- **Configuration**: pydantic-settings (2.7.0)

## Development Commands

### Docker Compose (推薦使用 Makefile)
專案使用 Docker Compose 進行開發，所有命令已整合至 Makefile：

```bash
# 建置並啟動所有服務
make build

# 啟動服務（不重新建置）
make up

# 停止服務
make down

# 停止服務並刪除 volumes
make down-v

# 查看 Docker Compose 配置
make bank-config

# 檢查網路配置
make inspect-network

# 連接到 PostgreSQL
make psql
```

### Database Migrations (Alembic)
```bash
# 生成新的 migration（需指定 name）
make makemigrations name="your_migration_name"

# 執行 migrations
make migrate

# 查看 migration 歷史
make history

# 查看當前 migration 版本
make current-migration

# 降級到特定版本（需指定 revision）
make downgrade revision="revision_id"
```

### Local Development (無 Docker)
```bash
cd src
pipenv install --dev  # Install all dependencies
pipenv shell          # Activate virtual environment

# 運行應用程式
pipenv run uvicorn backend.app.main:app --reload  # 開發模式（hot reload）
pipenv run uvicorn backend.app.main:app --host 0.0.0.0 --port 8000  # Production-like
```

### Code Formatting
The project uses Black formatter (configured in .vscode/settings.json):
```bash
pipenv run black backend/
```

### Type Checking
Type checking mode is set to "basic" via VS Code settings.

## Architecture

### Directory Structure
```
src/
├── backend/app/
│   ├── main.py                    # FastAPI 應用程式入口（lifespan, health check）
│   ├── core/                      # 核心功能模組
│   │   ├── config.py              # 環境配置（pydantic-settings）
│   │   ├── logging.py             # Loguru 日誌系統
│   │   ├── db.py                  # 資料庫連接池和 session 管理
│   │   ├── model_registry.py     # 自動發現和載入 models
│   │   ├── health.py              # 健康檢查系統（database, redis, celery）
│   │   ├── celery_app.py          # Celery .3+062配置和任務佇列
│   │   └── emails/                # 郵件系統
│   │       ├── config.py          # FastAPI-Mail 配置
│   │       ├── base.py            # 郵件發送基礎類別
│   │       ├── tasks.py           # Celery 郵件任務
│   │       └── templates/         # Jinja2 郵件模板（base.html/txt）
│   ├── api/                       # API 層
│   │   ├── main.py                # API router 聚合
│   │   └── routes/                # 路由模組
│   │       └── home.py            # 首頁路由
│   ├── auth/                      # 認證模組
│   │   ├── models.py              # User 模型（UUID, roles, OTP, 失敗登入追蹤）
│   │   ├── schema.py              # Pydantic schemas（角色、狀態、安全問題）
│   │   └── utils.py               # 密碼哈希、OTP 生成、用戶名生成
│   ├── logs/                      # 日誌檔案目錄
│   └── celerybeat/                # Celery Beat 排程檔案
├── migrations/                    # Alembic 遷移檔案
│   ├── env.py                     # Alembic 環境配置
│   └── versions/                  # Migration 版本
│       └── 7e1799408eb1_add_user_table.py
├── docs/                          # 技術規範文件
│   └── email_template.md          # Email 模板規範
├── .envs/                         # 環境變數檔案
├── alembic.ini                    # Alembic 配置
├── local.yml                      # Docker Compose 配置
├── Makefile                       # 開發命令快捷方式
└── CLAUDE.md                      # 本文件
```

### Configuration System (backend/app/core/config.py)
- Uses `pydantic-settings` (2.7.0) for environment-based configuration
- Environment files expected at `../../.envs/.env.local` (relative to config.py)
- Supports three environments: `local`, `staging`, `production`
- **Key settings**:
  - Application: `PROJECT_NAME`, `PROJECT_DESCRIPTION`, `API_V1_STR`, `SITE_NAME`, `ENVIRONMENT`
  - Database: `DATABASE_URL` (PostgreSQL async connection string)
  - Redis: `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`
  - RabbitMQ: `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD`
  - SMTP: `SMTP_HOST`, `SMTP_PORT`, `MAIL_FROM`, `MAIL_FROM_NAME`

### Logging System (backend/app/core/logging.py)
- Uses Loguru (0.7.3) for structured logging
- Two log files created in `backend/app/logs/`:
  - `debug.log` - DEBUG/INFO/WARNING messages (10 MB rotation, 30-day retention)
  - `errors.log` - ERROR/CRITICAL messages with backtrace (10 MB rotation, 30-day retention)
- Log level adjusts based on environment (DEBUG in local, INFO otherwise)
- Logs compressed to zip after rotation
- **Import logger using**: `from backend.app.core.logging import get_logger`

### API Structure
- All API routes prefixed with `settings.API_V1_STR`
- OpenAPI docs available at `{API_V1_STR}/docs` and `{API_V1_STR}/redoc`
- Routes organized by domain in `api/routes/` directory
- Each route module exports a router that gets included in `api/main.py`

### Database System (backend/app/core/db.py)
**已實現功能**：
- SQLModel (0.0.22) 用於 ORM
- Alembic (1.14.0) 用於資料庫遷移
- 非同步連接池：
  - asyncpg (0.30.0) - Async PostgreSQL driver
  - psycopg[binary,pool] - PostgreSQL adapter with connection pooling
  - Pool configuration: size=5, max_overflow=10, timeout=30s, recycle=1800s
- **Session 管理**：
  - `get_session()` - Async generator 提供 DB session
  - 自動 rollback 和 close 處理
  - 錯誤日誌記錄
- **初始化**：
  - `init_db()` - 載入模型註冊表並建立連接
  - 重試機制：最多 3 次，延遲遞增

### Model Registry (backend/app/core/model_registry.py)
- 自動發現專案中所有 `models.py` 檔案
- 動態匯入模型以確保 Alembic 能偵測到所有表格
- 使用 `load_models()` 函式在應用程式啟動時載入

### Health Check System (backend/app/core/health.py)
**完整健康檢查系統**：
- 支援的服務：Database, Redis, Celery
- **狀態類型**：HEALTHY, UNHEALTHY, DEGRADED, STARTING, DOWN
- **功能**：
  - 服務依賴管理
  - 重試機制（可配置次數和延遲）
  - 超時控制
  - 結果快取（25 秒）
  - 並行健康檢查
- **API endpoint**: `GET /health` 回傳所有服務狀態
- **啟動檢查**: 應用程式啟動時等待所有關鍵服務就緒（90 秒超時）

### Task Queue System (backend/app/core/celery_app.py)
**Celery 配置**：
- Broker: RabbitMQ
- Backend: Redis
- 序列化：JSON
- **設定**：
  - 預設佇列：`bank_tasks`
  - 任務時間限制：5 分鐘
  - 重試：最多 3 次，延遲 300 秒
  - Worker：每個子程序最多處理 100 個任務
  - 記憶體限制：50 MB per child
- **自動發現任務**：從 `backend.app.core.emails.tasks` 載入

### Email System (backend/app/core/emails/)
**已實現功能**：
- FastAPI-Mail (1.4.2) 整合
- Jinja2 模板引擎
- **配置檔案** (`config.py`):
  - SMTP 設定（Mailpit for local development）
  - 模板目錄：`backend/app/core/emails/templates/`
- **模板系統**：
  - Base 模板：`base.html` 和 `base.txt`
  - 支援 HTML 和純文字雙格式
  - **必須遵循** `/docs/email_template.md` 規範
- **Celery 任務** (`tasks.py`): 非同步郵件發送

### Authentication & User System (backend/app/auth/)

#### User Model (models.py)
**欄位**：
- `id` (UUID) - 主鍵，自動生成
- `username` (str) - 唯一，最大 30 字元
- `email` (EmailStr) - 唯一索引，最大 255 字元
- `first_name`, `last_name` (str) - 姓名，最大 50 字元
- `id_no` (int) - 身分證字號，唯一，正整數
- `hashed_password` (str) - Argon2 加密密碼
- `is_active`, `is_superuser` (bool)
- `security_question`, `security_answer` (str) - 安全問題和答案
- `account_status` (AccountStatusSchema) - 帳號狀態
- `role` (RoleCoiceSchema) - 使用者角色
- `failed_login_attempts` (int) - 失敗登入次數
- `last_failed_login` (datetime) - 最後失敗登入時間
- `otp`, `otp_expiry_time` - OTP 和過期時間
- `created_at`, `updated_at` (datetime) - 時間戳記

**方法**：
- `full_name` (computed_field) - 返回完整姓名
- `has_role(role)` - 檢查使用者角色

#### Schemas (schema.py)
**Enums**：
- `SecurityQuestionsSchema` - 6 種安全問題（繁體中文）
- `AccountStatusSchema` - ACTIVE, INACTIVE, LOCKED, PENDING
- `RoleCoiceSchema` - CUSTOMER, TELLER, ACCOUNT_EXECUTIVE, BRANCH_MANAGER, ADMIN, SUPER_ADMIN

**Schemas**：
- `BaseUserSchema` - 基礎使用者欄位
- `UserCreateSchema` - 包含密碼驗證邏輯

#### Utilities (utils.py)
**函式**：
- `generate_otp(length=6)` - 生成數字 OTP
- `generate_hashed_password(plain_password)` - Argon2 密碼哈希
- `verify_password(plain_password, hashed_password)` - 密碼驗證
- `generate_username()` - 自動生成用戶名（格式：`{SITE_NAME_PREFIX}-{RANDOM}`）

### Application Lifespan (backend/app/main.py)
**啟動流程**：
1. 初始化資料庫連接（`init_db()`）
2. 註冊健康檢查服務（database, redis, celery）
3. 執行啟動健康檢查（等待所有服務就緒，90 秒超時）
4. 啟動 FastAPI 應用程式

**關閉流程**：
1. 關閉資料庫引擎
2. 清理健康檢查資源

## Development Guidelines

### Adding New Routes
1. Create new router file in `backend/app/api/routes/`
2. Define router with prefix: `router = APIRouter(prefix="/your-prefix")`
3. Import and include router in `backend/app/api/main.py`
4. Use logger for debugging: `from backend.app.core.logging import get_logger`
5. All routes will automatically be prefixed with `settings.API_V1_STR`

### Adding New Models
1. Create or update `models.py` in the relevant module (e.g., `backend/app/auth/models.py`)
2. Models will be auto-discovered by `model_registry.py`
3. Generate migration: `make makemigrations name="descriptive_name"`
4. Review generated migration in `migrations/versions/`
5. Apply migration: `make migrate`

### Adding Email Templates
**必須嚴格遵循 `/docs/email_template.md` 規範**：
1. 先閱讀 `/docs/email_template.md`
2. 建立 HTML 版本：`backend/app/core/emails/templates/{name}.html`
3. 建立 TXT 版本：`backend/app/core/emails/templates/{name}.txt`
4. 兩個檔案都必須繼承對應的 base 模板
5. 使用台灣繁體中文商業用語
6. 所有樣式必須為 inline style
7. 不得包含敏感資訊（密碼、token 等）
8. 必須標註連結有效期限

### Adding Celery Tasks
1. 在相關模組中建立 `tasks.py`（例如：`backend/app/core/emails/tasks.py`）
2. 使用 `@celery_app.task` 裝飾器
3. 在 `backend/app/core/celery_app.py` 的 `autodiscover_tasks` 中新增模組路徑
4. 重啟 Celery worker 以載入新任務

### Database Session Usage
```python
from backend.app.core.db import get_session
from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

@router.get("/example")
async def example_endpoint(session: AsyncSession = Depends(get_session)):
    # Use session here
    result = await session.execute(select(User))
    return result.scalars().all()
```

### Logging Best Practices
```python
from backend.app.core.logging import get_logger

logger = get_logger()

# Log levels
logger.debug("Detailed debugging information")
logger.info("General informational messages")
logger.warning("Warning messages")
logger.error("Error messages")
logger.critical("Critical errors")

# With context
logger.info(f"User {user_id} logged in successfully")
```

### Password Hashing
```python
from backend.app.auth.utils import generate_hashed_password, verify_password

# Hash password
hashed = generate_hashed_password("user_password")

# Verify password
is_valid = verify_password("user_password", hashed)
```

## Docker Services

### Services in local.yml
- **api** - FastAPI application
- **postgres** - PostgreSQL 資料庫
- **redis** - Redis (Celery backend)
- **rabbitmq** - RabbitMQ (Celery broker)
- **celery_worker** - Celery worker
- **flower** - Celery monitoring (預設 port: 5555)
- **mailpit** - Email testing tool (預設 port: 8025 for UI, 1025 for SMTP)

### Accessing Services
- API: http://localhost:8000
- API Docs: http://localhost:8000{API_V1_STR}/docs
- Flower: http://localhost:5555
- Mailpit UI: http://localhost:8025
- PostgreSQL: localhost:5432

## Testing Emails Locally
1. 確保 Mailpit 正在運行（包含在 `make up` 中）
2. 訪問 http://localhost:8025 查看所有發送的郵件
3. 郵件不會真正發送到外部，所有郵件都會被 Mailpit 攔截並顯示在 UI 中

## Troubleshooting

### Services Not Starting
1. 檢查健康狀態：`curl http://localhost:8000/health`
2. 查看 logs：`docker compose -f local.yml logs api`
3. 檢查網路：`make inspect-network`
4. 重新建置：`make down-v && make build`

### Database Connection Issues
1. 確認 PostgreSQL 正在運行：`docker compose -f local.yml ps`
2. 檢查連接：`make psql`
3. 查看 migration 狀態：`make current-migration`

### Celery Tasks Not Running
1. 檢查 Celery worker logs：`docker compose -f local.yml logs celery_worker`
2. 檢查 RabbitMQ：`docker compose -f local.yml logs rabbitmq`
3. 檢查 Redis：`docker compose -f local.yml logs redis`
4. 使用 Flower 監控：http://localhost:5555

## Migration 相關注意事項
1. **自動生成的 migration 需要人工審查**，確保：
   - 欄位類型正確
   - 索引設置合理
   - 外鍵約束正確
   - 沒有遺漏的欄位
2. **Migration 命名規範**：使用描述性名稱（例如：`add_user_table`, `add_email_index_to_users`）
3. **測試 migration**：
   - 先在本地測試 upgrade 和 downgrade
   - 檢查資料完整性
4. **Migration 版本控制**：所有 migration 檔案必須納入 git 版本控制

## 專案當前狀態總結

### 已完成功能 ✅
- ✅ FastAPI 應用程式骨架
- ✅ 環境配置系統（pydantic-settings）
- ✅ 結構化日誌系統（Loguru）
- ✅ 資料庫連接池和 session 管理
- ✅ Alembic 遷移系統
- ✅ User 模型（包含角色、狀態、OTP、失敗登入追蹤）
- ✅ 密碼哈希和驗證（Argon2）
- ✅ Celery 任務佇列（RabbitMQ + Redis）
- ✅ 郵件系統（FastAPI-Mail + Jinja2 模板）
- ✅ 健康檢查系統（database, redis, celery）
- ✅ Docker Compose 開發環境
- ✅ Makefile 命令快捷方式
- ✅ 模型自動註冊系統

### 待開發功能 🚧
- 🚧 用戶註冊 API
- 🚧 用戶登入 API（JWT token）
- 🚧 密碼重置流程
- 🚧 Email 驗證流程（activation）
- 🚧 OTP 驗證
- 🚧 角色權限控制（RBAC）
- 🚧 API 路由保護（authentication middleware）
- 🚧 帳號管理相關 API
- 🚧 單元測試和整合測試
- 🚧 API 文件完善
