from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from . import models
from typing import List, Optional
from .services.auth_service import get_password_hash


async def get_journal_entries(
    db: AsyncSession, user_id: int, skip: int = 0, limit: int = 100
) -> List[models.TradeJournalEntry]:
    """讀取所有交易日誌"""
    result = await db.exec(
        select(models.TradeJournalEntry)
        .where(models.TradeJournalEntry.owner_id == user_id)
        .offset(skip)
        .limit(limit)
    )
    entries = result.all()
    return list(entries)


async def create_journal_entry(
    db: AsyncSession, entry: models.TradeJournalEntryCreate, user_id: int
) -> models.TradeJournalEntry:
    """建立一筆新的交易日誌"""
    db_entry = models.TradeJournalEntry(**entry.model_dump(), owner_id=user_id)
    db.add(db_entry)
    await db.commit()
    await db.refresh(db_entry)
    return db_entry


async def get_journal_entry(
    db: AsyncSession, entry_id: int
) -> models.TradeJournalEntry | None:
    """根據 ID 獲取單筆交易日誌"""
    return await db.get(models.TradeJournalEntry, entry_id)


async def get_user_by_username(
    db: AsyncSession, username: str
) -> Optional[models.User]:
    result = await db.exec(select(models.User).where(models.User.username == username))
    return result.first()


async def create_user(db: AsyncSession, user: models.UserCreate) -> models.User:
    hashed_password = get_password_hash(user.password)
    # 我們從 UserCreate 創建 User 資料庫物件
    db_user = models.User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user
