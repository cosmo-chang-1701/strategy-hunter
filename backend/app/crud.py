from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from . import models, schemas


async def get_journal_entries(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> list[models.TradeJournalEntry]:
    """讀取所有交易日誌"""
    result = await db.execute(
        select(models.TradeJournalEntry).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


async def create_journal_entry(
    db: AsyncSession, entry: schemas.TradeJournalEntryCreate
) -> models.TradeJournalEntry:
    """建立一筆新的交易日誌"""
    db_entry = models.TradeJournalEntry(**entry.model_dump())
    db.add(db_entry)
    await db.commit()
    await db.refresh(db_entry)
    return db_entry


async def get_journal_entry(
    db: AsyncSession, entry_id: int
) -> models.TradeJournalEntry | None:
    """根據 ID 獲取單筆交易日誌"""
    result = await db.execute(
        select(models.TradeJournalEntry).where(models.TradeJournalEntry.id == entry_id)
    )
    return result.scalar_one_or_none()
