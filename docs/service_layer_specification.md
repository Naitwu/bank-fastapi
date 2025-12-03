# Service Layer Specification (服務層規範)

本文件定義 FastAPI 應用程式中服務層（Service Layer）的設計標準和最佳實踐。

---

## 1. 服務層概述 (Service Layer Overview)

### 1.1 什麼是服務層？

服務層（Service Layer）是位於 **API 路由層（Routes）** 和 **資料模型層（Models）** 之間的業務邏輯層。

```
┌─────────────────────┐
│   API Routes        │  ← 處理 HTTP 請求/回應
│   (routes/)         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   Service Layer     │  ← 業務邏輯、流程編排
│   (services/)       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   Data Models       │  ← 資料庫模型、ORM
│   (models.py)       │
└─────────────────────┘
```

### 1.2 服務層的職責 (Responsibilities)

✅ **應該做的事**：
- 實作業務邏輯和業務規則
- 編排多個資料庫操作
- 處理複雜的資料轉換
- 整合外部服務（email, Celery 任務等）
- 驗證業務規則（非 Schema 層級的驗證）
- 管理交易（transactions）

❌ **不應該做的事**：
- 直接處理 HTTP 請求/回應（這是 Routes 的職責）
- 定義 Pydantic Schemas（這屬於 Schema 層）
- 包含 ORM 模型定義（這屬於 Models 層）
- 處理認證授權邏輯（使用 dependencies）

---

## 2. 服務層架構 (Service Layer Architecture)

### 2.1 目錄結構

```
backend/app/
├── api/
│   └── services/              # API 專用服務
│       ├── user_auth.py       # 用戶認證服務
│       ├── profile.py         # 用戶資料服務
│       ├── next_of_kin.py     # 緊急聯絡人服務
│       ├── bank_account.py    # 銀行帳戶服務
│       └── transaction.py     # 交易處理服務
│
├── core/
│   └── services/              # 核心/共享服務
│       ├── activation.py      # 帳戶啟用服務
│       ├── login_otp.py       # 登入 OTP 服務
│       ├── account_lockout.py # 帳戶鎖定服務
│       ├── password_reset.py  # 密碼重置服務
│       └── deposit_alert.py   # 存款通知服務
│
└── {module}/
    ├── models.py              # 模組的資料模型
    ├── schema.py              # 模組的 Pydantic Schemas
    └── routes.py              # 模組的 API 路由
```

### 2.2 API Services vs Core Services

#### API Services (`backend/app/api/services/`)

**用途**：處理特定 API 端點的業務邏輯

**特徵**：
- 通常與特定資源相關（users, accounts, transactions）
- 被 API routes 直接調用
- 包含 CRUD 操作的業務邏輯
- 可能調用多個 Core Services

**範例**：
```python
# backend/app/api/services/bank_account.py
class BankAccountService:
    """銀行帳戶相關業務邏輯"""

    async def create_account(self, user_id: UUID, account_data: dict, session: AsyncSession):
        """建立銀行帳戶並發送通知"""
        # 業務邏輯...

    async def activate_account(self, account_id: UUID, session: AsyncSession):
        """啟用銀行帳戶"""
        # 業務邏輯...
```

#### Core Services (`backend/app/core/services/`)

**用途**：提供跨模組的共享功能

**特徵**：
- 提供通用功能（email 發送、通知、外部 API 整合）
- 可被多個 API Services 調用
- 通常不直接被 routes 調用
- 封裝第三方服務整合

**範例**：
```python
# backend/app/core/services/activation.py
class ActivationEmailService:
    """帳戶啟用郵件服務"""

    async def send_activation_email(self, user: User, activation_token: str):
        """發送啟用郵件"""
        # Email 發送邏輯...
```

---

## 3. 服務類別設計 (Service Class Design)

### 3.1 命名規範 (Naming Conventions)

```python
# 格式：{Resource/Purpose}Service
UserAuthService          # 用戶認證服務
BankAccountService       # 銀行帳戶服務
TransactionService       # 交易服務
ActivationEmailService   # 啟用郵件服務
```

### 3.2 基本結構

```python
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid import UUID
from backend.app.core.logging import get_logger

logger = get_logger()


class ExampleService:
    """服務描述

    職責：
    - 職責 1
    - 職責 2
    """

    async def method_name(
        self,
        param1: Type1,
        param2: Type2,
        session: AsyncSession
    ) -> ReturnType:
        """方法說明

        Args:
            param1: 參數 1 說明
            param2: 參數 2 說明
            session: 資料庫 session

        Returns:
            回傳值說明

        Raises:
            Exception1: 何時拋出
            Exception2: 何時拋出
        """
        try:
            # 業務邏輯實作
            logger.info(f"Starting operation: {param1}")

            # ... 實作 ...

            logger.info(f"Operation completed successfully")
            return result

        except SpecificException as e:
            # 特定錯誤處理
            logger.error(f"Specific error: {str(e)}")
            raise

        except Exception as e:
            # 通用錯誤處理
            logger.error(f"Unexpected error: {str(e)}")
            raise
```

### 3.3 單例模式 (Singleton Pattern)

**所有服務類別應使用模組級單例模式**：

```python
# backend/app/api/services/bank_account.py

class BankAccountService:
    """銀行帳戶服務"""

    async def create_account(self, ...):
        pass

    async def activate_account(self, ...):
        pass


# 模組級單例
bank_account_service = BankAccountService()
```

**使用範例**：

```python
# backend/app/bank_account/routes.py
from backend.app.api.services.bank_account import bank_account_service

@router.post("/create")
async def create_bank_account(
    account_data: BankAccountCreateSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session)
):
    """建立銀行帳戶"""
    return await bank_account_service.create_account(
        user_id=current_user.id,
        account_data=account_data.model_dump(),
        session=session
    )
```

---

## 4. 職責分離範例 (Separation of Concerns Examples)

### 4.1 正確的分層 ✅

```python
# ============================================
# routes.py - API 路由層
# ============================================
from backend.app.api.services.bank_account import bank_account_service

@router.post("/bank-accounts/create", response_model=BankAccountReadSchema)
async def create_bank_account(
    account_data: BankAccountCreateSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session)
):
    """
    建立銀行帳戶

    職責：
    - 接收 HTTP 請求
    - 驗證 Schema
    - 調用服務層
    - 回傳 HTTP 回應
    """
    return await bank_account_service.create_account(
        user_id=current_user.id,
        account_data=account_data.model_dump(),
        session=session
    )


# ============================================
# services/bank_account.py - 服務層
# ============================================
from backend.app.core.services.bank_account_created import bank_account_created_service
from backend.app.bank_account.utils import generate_account_number

class BankAccountService:
    """銀行帳戶服務"""

    async def create_account(
        self,
        user_id: UUID,
        account_data: dict,
        session: AsyncSession
    ) -> BankAccount:
        """
        建立銀行帳戶

        職責：
        - 檢查用戶帳戶數量限制
        - 生成帳戶號碼
        - 建立帳戶記錄
        - 發送通知郵件
        """
        # 業務規則：檢查帳戶數量限制
        existing_accounts = await session.execute(
            select(func.count(BankAccount.id)).where(
                BankAccount.user_id == user_id
            )
        )
        account_count = existing_accounts.scalar_one()

        if account_count >= 3:
            raise ValueError("用戶最多只能擁有 3 個銀行帳戶")

        # 生成帳戶號碼
        account_number = generate_account_number()

        # 建立帳戶
        new_account = BankAccount(
            user_id=user_id,
            account_number=account_number,
            **account_data
        )

        session.add(new_account)
        await session.commit()
        await session.refresh(new_account)

        # 發送通知（異步任務）
        await bank_account_created_service.send_notification(new_account)

        return new_account


bank_account_service = BankAccountService()
```

### 4.2 錯誤的設計 ❌

```python
# ❌ 錯誤：在 routes 中直接寫業務邏輯
@router.post("/bank-accounts/create")
async def create_bank_account(
    account_data: BankAccountCreateSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session)
):
    # ❌ 業務邏輯不應該在 route 中
    existing_accounts = await session.execute(
        select(func.count(BankAccount.id)).where(
            BankAccount.user_id == current_user.id
        )
    )
    if existing_accounts.scalar_one() >= 3:
        raise HTTPException(status_code=400, detail="Too many accounts")

    # ❌ 資料庫操作不應該在 route 中
    account_number = generate_account_number()
    new_account = BankAccount(
        user_id=current_user.id,
        account_number=account_number,
        **account_data.model_dump()
    )
    session.add(new_account)
    await session.commit()

    # ❌ 外部服務整合不應該在 route 中
    send_email_task.delay(current_user.email, "Account Created")

    return new_account
```

---

## 5. 交易管理 (Transaction Management)

### 5.1 服務層負責交易邊界

**原則**：服務層方法應該定義交易邊界，確保資料一致性。

```python
class TransactionService:
    """交易處理服務"""

    async def process_deposit(
        self,
        account_id: UUID,
        amount: Decimal,
        session: AsyncSession
    ) -> Transaction:
        """
        處理存款交易

        此方法確保以下操作在同一交易中完成：
        1. 建立交易記錄
        2. 更新帳戶餘額
        3. 記錄審計日誌
        """
        try:
            # 1. 查詢帳戶
            account = await self._get_account(account_id, session)

            # 2. 建立交易記錄
            transaction = Transaction(
                account_id=account_id,
                transaction_type=TransactionTypeSchema.DEPOSIT,
                amount=amount,
                balance_before=account.balance,
                balance_after=account.balance + amount,
                status=TransactionStatusSchema.PENDING
            )
            session.add(transaction)

            # 3. 更新餘額
            account.balance += amount
            session.add(account)

            # 4. 提交交易
            await session.commit()

            # 5. 更新交易狀態
            transaction.status = TransactionStatusSchema.COMPLETED
            session.add(transaction)
            await session.commit()

            await session.refresh(transaction)

            logger.info(
                f"Deposit processed: account={account_id}, "
                f"amount={amount}, transaction={transaction.id}"
            )

            return transaction

        except Exception as e:
            # 發生錯誤時回滾
            await session.rollback()
            logger.error(f"Deposit failed: {str(e)}")
            raise


transaction_service = TransactionService()
```

### 5.2 處理部分失敗

```python
class BankAccountService:
    """銀行帳戶服務"""

    async def activate_account(
        self,
        account_id: UUID,
        session: AsyncSession
    ) -> BankAccount:
        """
        啟用銀行帳戶

        注意：郵件發送失敗不應該回滾帳戶啟用
        """
        try:
            # 1. 資料庫操作（需要交易保護）
            account = await self._get_account(account_id, session)

            if account.account_status == AccountStatusSchema.ACTIVE:
                raise ValueError("帳戶已經是啟用狀態")

            account.account_status = AccountStatusSchema.ACTIVE
            session.add(account)
            await session.commit()
            await session.refresh(account)

            logger.info(f"Account activated: {account_id}")

        except Exception as e:
            await session.rollback()
            logger.error(f"Account activation failed: {str(e)}")
            raise

        # 2. 郵件發送（不在交易中，失敗不回滾）
        try:
            await bank_account_activated_service.send_notification(account)
        except Exception as e:
            # 記錄錯誤但不拋出異常
            logger.error(
                f"Failed to send activation email for account {account_id}: {str(e)}"
            )

        return account


bank_account_service = BankAccountService()
```

---

## 6. 錯誤處理 (Error Handling)

### 6.1 服務層錯誤處理原則

1. **捕獲特定異常**：優先處理預期的異常類型
2. **記錄詳細日誌**：包含足夠的上下文資訊
3. **向上傳播**：讓 route 層決定 HTTP 狀態碼
4. **清理資源**：確保 session rollback

### 6.2 錯誤處理範例

```python
class UserAuthService:
    """用戶認證服務"""

    async def authenticate_user(
        self,
        email: str,
        password: str,
        session: AsyncSession
    ) -> User:
        """
        驗證用戶身份

        Raises:
            ValueError: 當用戶不存在或密碼錯誤時
            RuntimeError: 當帳戶被鎖定時
        """
        try:
            # 查詢用戶
            result = await session.execute(
                select(User).where(User.email == email)
            )
            user = result.scalar_one_or_none()

            # 用戶不存在
            if not user:
                logger.warning(f"Login attempt for non-existent user: {email}")
                raise ValueError("電子郵件或密碼錯誤")

            # 帳戶被鎖定
            if user.account_status == AccountStatusSchema.LOCKED:
                logger.warning(f"Login attempt for locked account: {email}")
                raise RuntimeError("帳戶已被鎖定，請聯絡客服")

            # 驗證密碼
            if not verify_password(password, user.hashed_password):
                # 增加失敗次數
                await self._increment_failed_attempts(user, session)
                logger.warning(f"Failed login attempt for user: {email}")
                raise ValueError("電子郵件或密碼錯誤")

            # 重置失敗次數
            await self._reset_failed_attempts(user, session)

            logger.info(f"User authenticated successfully: {user.id}")
            return user

        except (ValueError, RuntimeError):
            # 預期的業務錯誤，向上傳播
            raise

        except Exception as e:
            # 非預期錯誤
            logger.error(f"Unexpected error during authentication: {str(e)}")
            raise RuntimeError("驗證過程發生錯誤，請稍後再試")


user_auth_service = UserAuthService()
```

### 6.3 Route 層處理服務錯誤

```python
# routes.py
from backend.app.api.services.user_auth import user_auth_service

@router.post("/login")
async def login(
    credentials: LoginRequestSchema,
    session: AsyncSession = Depends(get_session)
):
    """用戶登入"""
    try:
        user = await user_auth_service.authenticate_user(
            email=credentials.email,
            password=credentials.password,
            session=session
        )

        # 生成 token...
        return {"access_token": token}

    except ValueError as e:
        # 業務驗證錯誤 -> 400
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
                "action": "請確認您的電子郵件和密碼"
            }
        )

    except RuntimeError as e:
        # 業務規則錯誤 -> 422
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "message": str(e),
                "action": "請聯絡客服以解鎖帳戶"
            }
        )

    except Exception as e:
        # 未預期錯誤 -> 500
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "登入時發生錯誤",
                "action": "請稍後再試"
            }
        )
```

---

## 7. 日誌記錄 (Logging)

### 7.1 日誌記錄原則

服務層應該記錄：
- ✅ 業務操作的開始和結束
- ✅ 業務規則驗證失敗
- ✅ 外部服務調用（成功/失敗）
- ✅ 資料庫操作錯誤
- ✅ 重要的業務決策點

不應該記錄：
- ❌ 敏感資訊（密碼、token、個人資料）
- ❌ 過於詳細的除錯資訊（production 環境）
- ❌ 每個方法調用（過多日誌）

### 7.2 日誌範例

```python
from backend.app.core.logging import get_logger

logger = get_logger()


class TransactionService:
    """交易服務"""

    async def process_transfer(
        self,
        from_account_id: UUID,
        to_account_id: UUID,
        amount: Decimal,
        session: AsyncSession
    ) -> Transaction:
        """處理轉帳"""

        # ✅ 記錄操作開始
        logger.info(
            f"Starting transfer: from={from_account_id}, "
            f"to={to_account_id}, amount={amount}"
        )

        try:
            # 驗證餘額
            from_account = await self._get_account(from_account_id, session)

            if from_account.balance < amount:
                # ✅ 記錄業務規則驗證失敗
                logger.warning(
                    f"Insufficient balance: account={from_account_id}, "
                    f"balance={from_account.balance}, required={amount}"
                )
                raise ValueError("餘額不足")

            # 執行轉帳...
            transaction = await self._execute_transfer(
                from_account_id, to_account_id, amount, session
            )

            # ✅ 記錄成功
            logger.info(
                f"Transfer completed: transaction={transaction.id}, "
                f"from={from_account_id}, to={to_account_id}, amount={amount}"
            )

            return transaction

        except ValueError:
            # 預期錯誤，已在上面記錄
            raise

        except Exception as e:
            # ✅ 記錄非預期錯誤
            logger.error(
                f"Transfer failed unexpectedly: from={from_account_id}, "
                f"to={to_account_id}, amount={amount}, error={str(e)}"
            )
            raise


transaction_service = TransactionService()
```

---

## 8. 整合外部服務 (External Service Integration)

### 8.1 Email 服務整合

```python
# backend/app/core/services/deposit_alert.py
from backend.app.core.emails.tasks import send_email_task

class DepositAlertService:
    """存款通知服務"""

    async def send_alert(self, transaction: Transaction, account: BankAccount):
        """發送存款通知郵件"""

        try:
            # 準備郵件內容
            context = {
                "account_number": account.account_number,
                "amount": str(transaction.amount),
                "currency": account.currency.value,
                "balance_before": str(transaction.balance_before),
                "balance_after": str(transaction.balance_after),
                "transaction_time": transaction.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "reference_number": transaction.reference_number,
            }

            # 使用 Celery 任務發送郵件（異步）
            send_email_task.delay(
                template_name="deposit_alert",
                recipient_email=account.user.email,
                subject="存款通知 - Deposit Alert",
                context=context
            )

            logger.info(
                f"Deposit alert email queued: account={account.id}, "
                f"transaction={transaction.id}"
            )

        except Exception as e:
            # 郵件發送失敗不應該影響主要業務流程
            logger.error(
                f"Failed to queue deposit alert email: "
                f"account={account.id}, error={str(e)}"
            )


deposit_alert_service = DepositAlertService()
```

### 8.2 Celery 任務整合

```python
class BankAccountService:
    """銀行帳戶服務"""

    async def create_account(
        self,
        user_id: UUID,
        account_data: dict,
        session: AsyncSession
    ) -> BankAccount:
        """建立銀行帳戶"""

        # ... 建立帳戶邏輯 ...

        # 發送通知郵件（異步任務）
        try:
            await bank_account_created_service.send_notification(new_account)
            logger.info(f"Notification email queued for account {new_account.id}")
        except Exception as e:
            # 郵件任務失敗不應該回滾帳戶建立
            logger.error(
                f"Failed to queue notification email: "
                f"account={new_account.id}, error={str(e)}"
            )

        return new_account


bank_account_service = BankAccountService()
```

---

## 9. 完整範例 (Complete Examples)

### 9.1 API Service 範例

```python
# backend/app/api/services/transaction.py
from decimal import Decimal
from uuid import UUID
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.core.logging import get_logger
from backend.app.transaction.models import Transaction
from backend.app.transaction.schema import TransactionTypeSchema, TransactionStatusSchema
from backend.app.bank_account.models import BankAccount
from backend.app.core.services.deposit_alert import deposit_alert_service

logger = get_logger()


class TransactionService:
    """交易處理服務

    職責：
    - 處理存款、提款、轉帳等交易
    - 確保交易原子性
    - 更新帳戶餘額
    - 發送交易通知
    """

    async def process_deposit(
        self,
        account_id: UUID,
        amount: Decimal,
        description: str | None,
        session: AsyncSession
    ) -> Transaction:
        """
        處理存款交易

        Args:
            account_id: 帳戶 ID
            amount: 存款金額
            description: 交易描述（選填）
            session: 資料庫 session

        Returns:
            Transaction: 完成的交易記錄

        Raises:
            ValueError: 當金額無效或帳戶狀態異常時
            RuntimeError: 當交易處理失敗時
        """
        logger.info(f"Processing deposit: account={account_id}, amount={amount}")

        try:
            # 1. 驗證金額
            if amount <= 0:
                raise ValueError("存款金額必須大於 0")

            # 2. 查詢並鎖定帳戶（防止並發問題）
            result = await session.execute(
                select(BankAccount)
                .where(BankAccount.id == account_id)
                .with_for_update()
            )
            account = result.scalar_one_or_none()

            if not account:
                raise ValueError("找不到指定的銀行帳戶")

            if account.account_status != "ACTIVE":
                raise ValueError("帳戶狀態異常，無法進行存款")

            # 3. 建立交易記錄
            balance_before = account.balance
            balance_after = balance_before + amount

            transaction = Transaction(
                account_id=account_id,
                transaction_type=TransactionTypeSchema.DEPOSIT,
                transaction_category="CREDIT",
                amount=amount,
                balance_before=balance_before,
                balance_after=balance_after,
                description=description,
                status=TransactionStatusSchema.PENDING
            )
            session.add(transaction)

            # 4. 更新帳戶餘額
            account.balance = balance_after
            session.add(account)

            # 5. 提交交易
            await session.commit()

            # 6. 更新交易狀態為完成
            transaction.status = TransactionStatusSchema.COMPLETED
            session.add(transaction)
            await session.commit()

            await session.refresh(transaction)

            logger.info(
                f"Deposit completed: transaction={transaction.id}, "
                f"account={account_id}, amount={amount}, "
                f"balance={balance_after}"
            )

        except (ValueError, RuntimeError):
            await session.rollback()
            raise

        except Exception as e:
            await session.rollback()
            logger.error(f"Deposit processing failed: {str(e)}")
            raise RuntimeError("處理存款時發生錯誤")

        # 7. 發送通知（不在交易中）
        try:
            await deposit_alert_service.send_alert(transaction, account)
        except Exception as e:
            logger.error(
                f"Failed to send deposit alert: "
                f"transaction={transaction.id}, error={str(e)}"
            )

        return transaction


transaction_service = TransactionService()
```

### 9.2 Core Service 範例

```python
# backend/app/core/services/activation.py
from backend.app.auth.models import User
from backend.app.core.emails.tasks import send_email_task
from backend.app.core.logging import get_logger
from backend.app.core.config import settings

logger = get_logger()


class ActivationEmailService:
    """帳戶啟用郵件服務

    職責：
    - 生成啟用連結
    - 發送啟用郵件
    - 處理郵件發送失敗
    """

    def _generate_activation_link(self, token: str) -> str:
        """生成啟用連結"""
        base_url = settings.SITE_URL
        return f"{base_url}/auth/activate/{token}"

    async def send_activation_email(
        self,
        user: User,
        activation_token: str
    ) -> None:
        """
        發送帳戶啟用郵件

        Args:
            user: 用戶對象
            activation_token: 啟用 token

        Raises:
            RuntimeError: 當郵件發送失敗時
        """
        try:
            activation_link = self._generate_activation_link(activation_token)

            context = {
                "user_name": user.full_name,
                "activation_link": activation_link,
                "site_name": settings.SITE_NAME,
                "valid_hours": 24,
            }

            # 使用 Celery 任務異步發送郵件
            send_email_task.delay(
                template_name="activation",
                recipient_email=user.email,
                subject="帳戶啟用 - Account Activation",
                context=context
            )

            logger.info(
                f"Activation email queued for user {user.id} ({user.email})"
            )

        except Exception as e:
            logger.error(
                f"Failed to queue activation email for user {user.id}: {str(e)}"
            )
            raise RuntimeError("無法發送啟用郵件，請稍後再試")


activation_email_service = ActivationEmailService()
```

---

## 10. 測試考量 (Testing Considerations)

### 10.1 服務層測試原則

1. **隔離測試**：使用測試資料庫，不依賴外部服務
2. **Mock 外部依賴**：Email、Celery 任務等
3. **測試業務邏輯**：專注於業務規則驗證
4. **測試錯誤處理**：確保異常正確處理

### 10.2 測試範例

```python
# tests/test_services/test_transaction.py
import pytest
from decimal import Decimal
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.services.transaction import transaction_service
from backend.app.bank_account.models import BankAccount
from backend.app.transaction.models import Transaction


@pytest.mark.asyncio
async def test_process_deposit_success(test_session: AsyncSession):
    """測試成功的存款流程"""

    # Arrange: 建立測試帳戶
    account = BankAccount(
        user_id=test_user.id,
        account_number="1234567890",
        balance=Decimal("1000.00"),
        account_status="ACTIVE"
    )
    test_session.add(account)
    await test_session.commit()

    # Act: 執行存款
    transaction = await transaction_service.process_deposit(
        account_id=account.id,
        amount=Decimal("500.00"),
        description="Test deposit",
        session=test_session
    )

    # Assert: 驗證結果
    await test_session.refresh(account)
    assert account.balance == Decimal("1500.00")
    assert transaction.amount == Decimal("500.00")
    assert transaction.status == "COMPLETED"


@pytest.mark.asyncio
async def test_process_deposit_invalid_amount(test_session: AsyncSession):
    """測試無效金額的存款"""

    # Arrange
    account = create_test_account(test_session)

    # Act & Assert
    with pytest.raises(ValueError, match="存款金額必須大於 0"):
        await transaction_service.process_deposit(
            account_id=account.id,
            amount=Decimal("-100.00"),
            description="Invalid deposit",
            session=test_session
        )
```

---

## 11. 檢查清單 (Checklist)

在建立新的服務類別時，請確認以下項目：

### 服務設計
- [ ] 服務類別命名遵循 `{Resource}Service` 格式
- [ ] 使用模組級單例模式（`service_name = ServiceClass()`）
- [ ] 類別有清晰的 docstring 說明職責
- [ ] 放置在正確的目錄（`api/services/` 或 `core/services/`）

### 方法設計
- [ ] 方法名稱清楚描述功能（動詞開頭）
- [ ] 所有方法都是 `async` 函數
- [ ] 參數使用正確的型別標註
- [ ] 有清晰的 docstring（包含 Args, Returns, Raises）
- [ ] `session` 參數放在最後

### 業務邏輯
- [ ] 業務規則在服務層實作（不在 routes）
- [ ] 複雜驗證邏輯在服務層處理
- [ ] 資料轉換邏輯封裝在服務層
- [ ] 不直接處理 HTTP 請求/回應

### 交易管理
- [ ] 使用 try-except 包裝資料庫操作
- [ ] 錯誤時執行 `await session.rollback()`
- [ ] 成功時執行 `await session.commit()`
- [ ] 多步驟操作在同一交易中完成

### 錯誤處理
- [ ] 捕獲特定異常類型
- [ ] 使用有意義的錯誤訊息
- [ ] 錯誤時記錄日誌
- [ ] 向上傳播異常（讓 route 決定 HTTP 狀態碼）

### 日誌記錄
- [ ] 重要操作開始時記錄 INFO 日誌
- [ ] 操作成功時記錄 INFO 日誌
- [ ] 業務規則驗證失敗記錄 WARNING 日誌
- [ ] 錯誤時記錄 ERROR 日誌
- [ ] 日誌包含足夠的上下文資訊
- [ ] 不記錄敏感資訊

### 外部服務整合
- [ ] Email 發送使用 Celery 任務（異步）
- [ ] 外部服務失敗不回滾主要業務
- [ ] 外部服務錯誤有適當的日誌記錄
- [ ] 使用 try-except 處理外部服務失敗

### 程式碼品質
- [ ] 遵循 PEP 8 風格規範
- [ ] 使用 Black 格式化程式碼
- [ ] 沒有重複程式碼（DRY 原則）
- [ ] 方法長度合理（建議 < 50 行）
- [ ] 有適當的型別標註

---

## 12. 參考資料 (References)

### 內部文件
- `CLAUDE.md` - 專案總覽和開發指南
- `/docs/api_route_specification.md` - API 路由規範
- `/docs/email_template.md` - Email 模板規範

### 設計模式
- **Service Layer Pattern** - 業務邏輯封裝
- **Repository Pattern** - 資料存取抽象（本專案使用 SQLModel 直接操作）
- **Dependency Injection** - 依賴注入（透過 FastAPI Depends）

### 外部資源
- [FastAPI Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [SQLModel Async Sessions](https://sqlmodel.tiangolo.com/tutorial/async/)
- [Domain-Driven Design](https://martinfowler.com/bliki/DomainDrivenDesign.html)

---

**版本**: 1.0.0
**最後更新**: 2025-12-02
**維護者**: Development Team
