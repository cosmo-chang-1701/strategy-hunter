from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

# 資料庫檔案的路徑
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./trade_journal.db"

# 建立非同步的資料庫引擎
engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# 建立一個 Session 工廠，我們之後會用它來建立與資料庫的對話
SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 建立一個基礎類，我們的 ORM 模型將會繼承它
Base = declarative_base()
