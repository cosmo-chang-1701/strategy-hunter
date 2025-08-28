import pytest_asyncio
from typing import AsyncGenerator
from fastapi.testclient import TestClient
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
from app.database import get_session as get_db_session

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# 1. 使用非同步引擎
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)

# 2. 使用 `async_sessionmaker` 來建立非同步 session 工廠
#    這會確保產生的 session 物件支援 `async with`
TestingSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=test_engine, class_=AsyncSession
)


# 3. 覆寫應用程式的 session 依賴，使其在測試中使用測試資料庫
async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db_session] = override_get_session


@pytest_asyncio.fixture(scope="function", name="client")
# 4. 修正 fixture 的返回類型註解
async def client_fixture() -> AsyncGenerator[TestClient, None]:
    # 5. 在測試開始前清除所有資料表後重新建立
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

    # 6. 使用 `with` 陳述式來確保 TestClient 被正確關閉
    with TestClient(app) as test_client:
        yield test_client

    # 7. 在測試結束後刪除所有資料表，保持測試環境乾淨
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
