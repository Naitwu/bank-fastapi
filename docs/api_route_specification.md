# API Route Specification (API 路由規範)

本文件定義 FastAPI 應用程式中 API 路由的設計標準和最佳實踐。

---

## 1. Route 命名規範 (Route Naming Conventions)

### 1.1 URL 路徑設計 (URL Path Design)

#### 基本原則
- ✅ 使用小寫字母和連字符（kebab-case）
- ✅ 使用複數名詞表示資源集合
- ✅ 路徑應具描述性且簡潔
- ✅ 避免動詞，使用 HTTP 方法表達動作
- ❌ 不使用底線（underscore）
- ❌ 不使用駝峰式命名（camelCase）

#### 正確範例
```python
# ✅ 良好的路徑設計
/api/v1/users
/api/v1/users/{user_id}
/api/v1/bank-accounts
/api/v1/bank-accounts/{account_id}/transactions
/api/v1/auth/login
/api/v1/auth/password-reset/request
```

#### 錯誤範例
```python
# ❌ 避免的設計
/api/v1/getUsers                    # 不要在路徑中使用動詞
/api/v1/user                        # 單數形式（應使用複數）
/api/v1/bank_accounts              # 底線（應使用連字符）
/api/v1/bankAccounts               # 駝峰式（應使用 kebab-case）
/api/v1/users/create               # 動作應用 HTTP POST 表達
```

### 1.2 路由前綴 (Route Prefix)

所有 API 路由必須使用版本前綴：

```python
from backend.app.core.config import settings

router = APIRouter(prefix="/users", tags=["Users"])
# 最終路徑會是：{settings.API_V1_STR}/users
```

**注意**：不要在 router prefix 中重複加入 `API_V1_STR`，main.py 會自動處理。

---

## 2. HTTP 方法選擇指南 (HTTP Method Selection)

### 2.1 標準 CRUD 操作

| 操作 | HTTP 方法 | 路徑範例 | 說明 |
|------|-----------|----------|------|
| 列出資源 (List) | GET | `/users` | 取得資源列表 |
| 取得單一資源 (Retrieve) | GET | `/users/{user_id}` | 取得特定資源 |
| 建立資源 (Create) | POST | `/users` | 建立新資源 |
| 完整更新 (Full Update) | PUT | `/users/{user_id}` | 完整替換資源 |
| 部分更新 (Partial Update) | PATCH | `/users/{user_id}` | 部分更新資源 |
| 刪除資源 (Delete) | DELETE | `/users/{user_id}` | 刪除資源 |

### 2.2 非 CRUD 操作

對於非標準 CRUD 操作，使用 POST 方法配合描述性路徑：

```python
# ✅ 正確：使用 POST 配合描述性路徑
POST /auth/login
POST /auth/logout
POST /auth/password-reset/request
POST /auth/password-reset/confirm
POST /bank-accounts/{account_id}/activate
POST /bank-accounts/{account_id}/deposit
POST /bank-accounts/{account_id}/withdraw

# ❌ 錯誤：不要使用 GET 執行有副作用的操作
GET /users/{user_id}/activate        # 應使用 POST
GET /accounts/{account_id}/close     # 應使用 POST
```

### 2.3 冪等性考量 (Idempotency)

- **GET, PUT, DELETE** - 必須是冪等的（多次執行結果相同）
- **POST** - 通常不是冪等的（每次執行可能產生新資源）
- **PATCH** - 視實作而定，建議設計為冪等

---

## 3. Request Schema 設計 (Request Schema Design)

### 3.1 Schema 命名規範

```python
# 基本模式
{ResourceName}{Action}Schema

# 範例
UserCreateSchema          # 建立用戶
UserUpdateSchema          # 更新用戶
LoginRequestSchema        # 登入請求
PasswordResetRequestSchema # 密碼重置請求
DepositRequestSchema      # 存款請求
```

### 3.2 Request Body 結構

```python
from pydantic import BaseModel, Field, field_validator

class UserCreateSchema(BaseModel):
    """用戶建立請求 Schema"""

    # 使用 Field 提供驗證和文件說明
    email: str = Field(
        ...,
        description="用戶電子郵件",
        examples=["user@example.com"]
    )
    first_name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="名字"
    )
    password: str = Field(
        ...,
        min_length=8,
        description="密碼（至少 8 個字元）"
    )

    # 使用 field_validator 進行複雜驗證
    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        # 驗證邏輯
        return v.lower()
```

### 3.3 Query Parameters（查詢參數）

```python
from fastapi import Query

@router.get("/users")
async def list_users(
    limit: int = Query(10, ge=1, le=100, description="每頁筆數"),
    offset: int = Query(0, ge=0, description="偏移量"),
    is_active: bool | None = Query(None, description="是否啟用"),
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    列出用戶

    - **limit**: 每頁筆數（1-100，預設 10）
    - **offset**: 偏移量（預設 0）
    - **is_active**: 過濾條件（選填）
    """
    pass
```

### 3.4 Path Parameters（路徑參數）

```python
from uuid import UUID

@router.get("/users/{user_id}")
async def get_user(
    user_id: UUID,  # 自動驗證 UUID 格式
    session: AsyncSession = Depends(get_session)
):
    """取得特定用戶"""
    pass
```

---

## 4. Response Schema 設計 (Response Schema Design)

### 4.1 成功回應結構 (Success Response)

#### 標準資源回應
```python
from datetime import datetime
from uuid import UUID

class UserReadSchema(BaseModel):
    """用戶讀取回應 Schema"""

    id: UUID
    email: str
    first_name: str
    last_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

#### 列表回應（含分頁）
```python
class PaginatedResponse(BaseModel, Generic[T]):
    """分頁回應通用格式"""

    data: list[T]
    total: int
    limit: int
    offset: int
    has_more: bool

# 使用範例
@router.get("/users", response_model=PaginatedResponse[UserReadSchema])
async def list_users(...):
    pass
```

#### 操作成功回應
```python
class SuccessResponse(BaseModel):
    """標準成功回應"""

    status: str = "success"
    message: str
    data: dict | None = None

# 使用範例
@router.post("/bank-accounts/{account_id}/activate")
async def activate_account(...) -> SuccessResponse:
    return SuccessResponse(
        status="success",
        message="帳戶已成功啟用",
        data={"account_id": str(account_id)}
    )
```

### 4.2 錯誤回應結構 (Error Response)

```python
class ErrorResponse(BaseModel):
    """標準錯誤回應"""

    status: str = "error"
    message: str  # 使用者友善的錯誤訊息
    action: str | None = None  # 建議使用者的下一步動作

# 使用範例
raise HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail={
        "status": "error",
        "message": "帳戶已被鎖定",
        "action": "請聯絡客服重設帳戶"
    }
)
```

---

## 5. 錯誤處理標準 (Error Handling Standards)

### 5.1 HTTP 狀態碼選擇

| 狀態碼 | 使用情境 | 範例 |
|--------|----------|------|
| 200 OK | 成功（GET, PATCH, PUT） | 取得用戶資料成功 |
| 201 Created | 資源建立成功（POST） | 用戶註冊成功 |
| 204 No Content | 成功但無回應內容（DELETE） | 刪除資源成功 |
| 400 Bad Request | 請求格式錯誤或驗證失敗 | 密碼格式不正確 |
| 401 Unauthorized | 未認證或 token 無效 | 未登入或 token 過期 |
| 403 Forbidden | 已認證但無權限 | 非管理員訪問管理功能 |
| 404 Not Found | 資源不存在 | 用戶 ID 不存在 |
| 409 Conflict | 資源衝突 | Email 已被註冊 |
| 422 Unprocessable Entity | 語法正確但語意錯誤 | 餘額不足無法提款 |
| 500 Internal Server Error | 伺服器錯誤 | 資料庫連接失敗 |

### 5.2 HTTPException 使用模式

```python
from fastapi import HTTPException, status

# ✅ 正確：使用結構化的 detail
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={
        "status": "error",
        "message": "找不到指定的銀行帳戶",
        "action": "請確認帳戶號碼是否正確"
    }
)

# ❌ 錯誤：使用字串 detail（缺乏結構化資訊）
raise HTTPException(
    status_code=404,
    detail="Account not found"
)
```

### 5.3 常見錯誤處理範例

```python
from sqlmodel import select
from backend.app.core.logging import get_logger

logger = get_logger()

@router.get("/users/{user_id}")
async def get_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_session)
):
    """取得特定用戶"""

    try:
        # 查詢資料庫
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        # 資源不存在
        if not user:
            logger.warning(f"User not found: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "message": "找不到指定的用戶",
                    "action": "請確認用戶 ID 是否正確"
                }
            )

        return user

    except HTTPException:
        # 重新拋出 HTTPException
        raise
    except Exception as e:
        # 記錄未預期的錯誤
        logger.error(f"Error fetching user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "取得用戶資料時發生錯誤",
                "action": "請稍後再試或聯絡技術支援"
            }
        )
```

---

## 6. 認證與授權 (Authentication & Authorization)

### 6.1 使用 CurrentUser Dependency

```python
from backend.app.auth.utils import get_current_user
from backend.app.auth.models import User

# CurrentUser type alias
CurrentUser = Annotated[User, Depends(get_current_user)]

@router.get("/profile/me")
async def get_current_user_profile(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session)
):
    """取得當前用戶資料（需認證）"""
    return current_user
```

### 6.2 角色權限檢查

```python
from backend.app.auth.schema import RoleChoiceSchema

def require_role(*allowed_roles: RoleChoiceSchema):
    """角色權限檢查裝飾器"""

    def role_checker(current_user: CurrentUser) -> User:
        if not current_user.has_role(*allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "message": "您沒有權限執行此操作",
                    "action": "請聯絡管理員獲取必要權限"
                }
            )
        return current_user

    return role_checker

# 使用範例
@router.delete("/users/{user_id}")
async def delete_user(
    user_id: UUID,
    current_user: Annotated[User, Depends(require_role(
        RoleChoiceSchema.ADMIN,
        RoleChoiceSchema.SUPER_ADMIN
    ))],
    session: AsyncSession = Depends(get_session)
):
    """刪除用戶（僅管理員）"""
    pass
```

### 6.3 公開路由（無需認證）

```python
# 不使用 CurrentUser dependency
@router.post("/auth/register")
async def register_user(
    user_data: UserCreateSchema,
    session: AsyncSession = Depends(get_session)
):
    """用戶註冊（公開 API）"""
    pass
```

---

## 7. 分頁標準 (Pagination Standards)

### 7.1 Offset-Based Pagination（偏移分頁）

**適用情境**：一般列表查詢

```python
from typing import TypeVar, Generic

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """分頁回應格式"""

    data: list[T]
    total: int
    limit: int
    offset: int
    has_more: bool

@router.get("/users", response_model=PaginatedResponse[UserReadSchema])
async def list_users(
    limit: int = Query(10, ge=1, le=100, description="每頁筆數"),
    offset: int = Query(0, ge=0, description="偏移量"),
    session: AsyncSession = Depends(get_session)
):
    """列出用戶（分頁）"""

    # 計算總數
    count_result = await session.execute(select(func.count(User.id)))
    total = count_result.scalar_one()

    # 查詢資料
    result = await session.execute(
        select(User)
        .limit(limit)
        .offset(offset)
        .order_by(User.created_at.desc())
    )
    users = result.scalars().all()

    return PaginatedResponse(
        data=users,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + limit < total
    )
```

### 7.2 Cursor-Based Pagination（遊標分頁）

**適用情境**：即時資料流、大數據集

```python
from datetime import datetime

class CursorPaginatedResponse(BaseModel, Generic[T]):
    """遊標分頁回應格式"""

    data: list[T]
    next_cursor: str | None
    has_more: bool

@router.get("/transactions", response_model=CursorPaginatedResponse[TransactionReadSchema])
async def list_transactions(
    cursor: str | None = Query(None, description="分頁遊標"),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session)
):
    """列出交易記錄（遊標分頁）"""

    query = select(Transaction).order_by(Transaction.created_at.desc())

    # 如果有 cursor，從該位置繼續查詢
    if cursor:
        cursor_dt = datetime.fromisoformat(cursor)
        query = query.where(Transaction.created_at < cursor_dt)

    # 多查一筆判斷是否有下一頁
    result = await session.execute(query.limit(limit + 1))
    transactions = result.scalars().all()

    has_more = len(transactions) > limit
    if has_more:
        transactions = transactions[:limit]

    next_cursor = None
    if has_more and transactions:
        next_cursor = transactions[-1].created_at.isoformat()

    return CursorPaginatedResponse(
        data=transactions,
        next_cursor=next_cursor,
        has_more=has_more
    )
```

---

## 8. API 版本控制 (API Versioning)

### 8.1 版本前綴

所有 API 路由透過 `settings.API_V1_STR` 統一管理版本：

```python
# backend/app/api/main.py
from backend.app.core.config import settings

api_router = APIRouter()
api_router.include_router(users_router, prefix="/users", tags=["Users"])

# backend/app/main.py
app.include_router(api_router, prefix=settings.API_V1_STR)
```

### 8.2 版本升級策略

**新增 v2 時的作法**：

1. 更新 `config.py` 新增 `API_V2_STR`
2. 建立 `backend/app/api/v2/` 目錄
3. 在 `main.py` 中新增 v2 router
4. 保持 v1 向後相容，設定棄用警告

---

## 9. 完整範例 (Complete Example)

### 9.1 標準 CRUD API

```python
from fastapi import APIRouter, Depends, Query, status
from uuid import UUID
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.auth.utils import get_current_user
from backend.app.auth.models import User
from backend.app.next_of_kin.models import NextOfKin
from backend.app.next_of_kin.schema import (
    NextOfKinCreateSchema,
    NextOfKinReadSchema,
    NextOfKinUpdateSchema
)

router = APIRouter(prefix="/next-of-kin", tags=["Next of Kin"])
logger = get_logger()

CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post(
    "/create",
    response_model=NextOfKinReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="建立緊急聯絡人",
    description="為當前用戶建立新的緊急聯絡人資訊"
)
async def create_next_of_kin(
    next_of_kin_data: NextOfKinCreateSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session)
) -> NextOfKin:
    """
    建立緊急聯絡人

    - **first_name**: 名字
    - **last_name**: 姓氏
    - **phone_number**: 電話號碼
    - **relationship**: 關係
    """
    try:
        # 建立新記錄
        new_next_of_kin = NextOfKin(
            **next_of_kin_data.model_dump(),
            user_id=current_user.id
        )

        session.add(new_next_of_kin)
        await session.commit()
        await session.refresh(new_next_of_kin)

        logger.info(
            f"Next of kin created for user {current_user.id}: "
            f"{new_next_of_kin.id}"
        )

        return new_next_of_kin

    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating next of kin: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "建立緊急聯絡人時發生錯誤",
                "action": "請稍後再試"
            }
        )


@router.get(
    "/all",
    response_model=list[NextOfKinReadSchema],
    summary="取得所有緊急聯絡人",
    description="取得當前用戶的所有緊急聯絡人列表"
)
async def get_all_next_of_kin(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session)
) -> list[NextOfKin]:
    """取得所有緊急聯絡人"""
    try:
        result = await session.execute(
            select(NextOfKin)
            .where(NextOfKin.user_id == current_user.id)
            .order_by(NextOfKin.created_at.desc())
        )
        next_of_kin_list = result.scalars().all()

        return next_of_kin_list

    except Exception as e:
        logger.error(f"Error fetching next of kin: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "取得緊急聯絡人時發生錯誤",
                "action": "請稍後再試"
            }
        )


@router.patch(
    "/update",
    response_model=NextOfKinReadSchema,
    summary="更新緊急聯絡人",
    description="更新指定的緊急聯絡人資訊"
)
async def update_next_of_kin(
    next_of_kin_id: UUID,
    update_data: NextOfKinUpdateSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session)
) -> NextOfKin:
    """更新緊急聯絡人"""
    try:
        # 查詢記錄
        result = await session.execute(
            select(NextOfKin).where(
                NextOfKin.id == next_of_kin_id,
                NextOfKin.user_id == current_user.id
            )
        )
        next_of_kin = result.scalar_one_or_none()

        if not next_of_kin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "message": "找不到指定的緊急聯絡人",
                    "action": "請確認 ID 是否正確"
                }
            )

        # 更新欄位
        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(next_of_kin, key, value)

        session.add(next_of_kin)
        await session.commit()
        await session.refresh(next_of_kin)

        logger.info(f"Next of kin updated: {next_of_kin.id}")

        return next_of_kin

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating next of kin: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "更新緊急聯絡人時發生錯誤",
                "action": "請稍後再試"
            }
        )


@router.delete(
    "/delete",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除緊急聯絡人",
    description="刪除指定的緊急聯絡人"
)
async def delete_next_of_kin(
    next_of_kin_id: UUID,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session)
) -> None:
    """刪除緊急聯絡人"""
    try:
        # 查詢記錄
        result = await session.execute(
            select(NextOfKin).where(
                NextOfKin.id == next_of_kin_id,
                NextOfKin.user_id == current_user.id
            )
        )
        next_of_kin = result.scalar_one_or_none()

        if not next_of_kin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "message": "找不到指定的緊急聯絡人",
                    "action": "請確認 ID 是否正確"
                }
            )

        await session.delete(next_of_kin)
        await session.commit()

        logger.info(f"Next of kin deleted: {next_of_kin.id}")

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Error deleting next of kin: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "刪除緊急聯絡人時發生錯誤",
                "action": "請稍後再試"
            }
        )
```

---

## 10. 檢查清單 (Checklist)

在建立新的 API 路由時，請確認以下項目：

### 路由設計
- [ ] URL 使用 kebab-case（小寫 + 連字符）
- [ ] 使用複數名詞表示資源集合
- [ ] HTTP 方法選擇正確（GET/POST/PUT/PATCH/DELETE）
- [ ] Router 使用正確的 prefix 和 tags
- [ ] 路由有清晰的 summary 和 description

### Schema 設計
- [ ] Request schema 命名遵循 `{Resource}{Action}Schema` 格式
- [ ] Response schema 使用 `{Resource}ReadSchema` 格式
- [ ] 使用 `Field()` 提供驗證和文件說明
- [ ] 複雜驗證使用 `field_validator`
- [ ] Response schema 設定 `model_config = ConfigDict(from_attributes=True)`

### 錯誤處理
- [ ] 所有錯誤使用結構化 detail（status, message, action）
- [ ] HTTP 狀態碼選擇正確
- [ ] 資源不存在回傳 404
- [ ] 驗證失敗回傳 400
- [ ] 權限不足回傳 403
- [ ] 未預期錯誤有 try-except 並記錄日誌

### 認證授權
- [ ] 需要認證的路由使用 `CurrentUser` dependency
- [ ] 需要特定角色的路由使用 `require_role()`
- [ ] 公開路由不使用認證 dependency

### 日誌記錄
- [ ] 重要操作記錄 INFO 日誌
- [ ] 錯誤記錄 ERROR 日誌
- [ ] 日誌包含足夠的上下文資訊（user_id, resource_id 等）

### 資料庫操作
- [ ] 使用 `AsyncSession` dependency
- [ ] 錯誤時執行 `await session.rollback()`
- [ ] 成功時執行 `await session.commit()`
- [ ] 需要回傳最新資料時執行 `await session.refresh()`

### 分頁
- [ ] 列表 API 實作分頁（offset-based 或 cursor-based）
- [ ] 分頁參數有合理的預設值和限制
- [ ] 回傳總數和 `has_more` 資訊

### 文件
- [ ] Docstring 描述端點功能
- [ ] 參數說明清楚
- [ ] OpenAPI schema 正確（在 `/docs` 檢視）

---

## 11. 參考資料 (References)

### 內部文件
- `CLAUDE.md` - 專案總覽和開發指南
- `/docs/service_layer_specification.md` - 服務層規範
- `/docs/schema_design_specification.md` - Schema 設計規範

### 外部資源
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [REST API Best Practices](https://restfulapi.net/)
- [HTTP Status Codes](https://httpstatuses.com/)

---

**版本**: 1.0.0
**最後更新**: 2025-12-02
**維護者**: Development Team
