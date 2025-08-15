from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional
from datetime import datetime
from sqlalchemy import Column, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import declared_attr


# ------------------------------------------------------------------
# 交易日誌 (Trade Journal) 的模型
# ------------------------------------------------------------------
# TradeJournalEntryBase 定義了所有日誌共用的欄位
# 它同時是 Pydantic 模型也是 SQLAlchemy 模型的基礎
class TradeJournalEntryBase(SQLModel):
    underlying: str = Field(default="SPY", index=True, description="標的")
    strategy: str = Field(default="Iron Condor", description="策略")
    entry_price: float = Field(default=1.50, description="進場價格/權利金")
    quantity: int = Field(default=10, description="合約數量")
    rationale: Optional[str] = Field(
        default="預期市場將在區間內盤整", description="交易理由"
    )
    exit_date: Optional[datetime] = Field(default=None, description="出場日期")
    exit_price: Optional[float] = Field(default=None, description="出場價格/權利金")
    final_pl: Optional[float] = Field(default=None, description="最終損益")


# TradeJournalEntry 是資料庫中的資料表模型
class TradeJournalEntry(TradeJournalEntryBase, table=True):
    @declared_attr  # type: ignore
    def __tablename__(cls) -> str:
        return "trade_journal_entries"

    id: Optional[int] = Field(default=None, primary_key=True)
    entry_date: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
        description="進場日期",
    )
    created_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )

    # 建立與 User 表的關聯
    owner_id: int = Field(foreign_key="users.id")
    owner: "User" = Relationship(back_populates="journal_entries")


# TradeJournalEntryCreate 是 API 建立日誌時使用的模型 (不包含 server-side 欄位)
class TradeJournalEntryCreate(TradeJournalEntryBase):
    pass


# TradeJournalEntryRead 是 API 回傳日誌時使用的模型 (包含所有欄位)
class TradeJournalEntryRead(TradeJournalEntryBase):
    id: int
    owner_id: int
    entry_date: datetime


# ------------------------------------------------------------------
# 使用者 (User) 的模型
# ------------------------------------------------------------------


# UserBase 定義了共用欄位
class UserBase(SQLModel):
    username: str = Field(index=True, unique=True)


# User 是資料庫中的資料表模型
class User(UserBase, table=True):
    @declared_attr  # type: ignore
    def __tablename__(cls) -> str:
        return "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    is_active: bool = True

    # 建立與交易日誌的反向關聯
    journal_entries: List[TradeJournalEntry] = Relationship(back_populates="owner")


# UserCreate 是 API 建立使用者時使用的模型 (需要密碼)
class UserCreate(UserBase):
    password: str


# UserRead 是 API 回傳使用者資訊時使用的模型 (不應包含密碼)
class UserRead(UserBase):
    id: int


# Token 是 API 回傳的認證令牌模型
class Token(SQLModel):
    access_token: str
    token_type: str


# TokenData 是 JWT 相關的模型
class TokenData(SQLModel):
    username: Optional[str] = None


# 動態地將 UserRead 模型與 TradeJournalEntryRead 產生關聯，避免循環 import
# 這一步驟讓 FastAPI 在回傳 UserRead 時，能正確地處理 journal_entries 欄位
# TradeJournalEntryRead.model_rebuild()
