from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from .database import Base


class TradeJournalEntry(Base):
    __tablename__ = "trade_journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    underlying = Column(String, index=True, comment="標的")
    strategy = Column(String, comment="策略")
    entry_date = Column(
        DateTime(timezone=True), server_default=func.now(), comment="進場日期"
    )
    exit_date = Column(DateTime(timezone=True), nullable=True, comment="出場日期")
    entry_price = Column(Float, comment="進場價格/權利金")
    exit_price = Column(Float, nullable=True, comment="出場價格/權利金")
    quantity = Column(Integer, comment="合約數量")
    rationale = Column(String, nullable=True, comment="交易理由")
    final_pl = Column(Float, nullable=True, comment="最終損益")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
