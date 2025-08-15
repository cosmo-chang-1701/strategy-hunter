from typing import AsyncGenerator
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from .config import settings

# The database file path
SQLALCHEMY_DATABASE_URL = settings.SQLALCHEMY_DATABASE_URL

# Create an asynchronous database engine
# The `echo` parameter is set based on the app's debug mode for better performance in production.
engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=settings.APP_DEBUG)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, autocommit=False, autoflush=False
)


async def init_db():
    """
    Initializes the database.
    In a production environment, consider using a migration tool like Alembic.
    """
    async with engine.begin() as conn:
        # This is for development, it will drop and recreate the tables
        # await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function that yields a new SQLAlchemy async session.
    """
    async with AsyncSessionLocal() as session:
        yield session
