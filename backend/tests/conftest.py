import pytest
import pytest_asyncio
from typing import AsyncGenerator
from fastapi.testclient import TestClient
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import respx

from app.main import app, check_polygon_options_access
from app.database import get_session as get_db_session
from app import database as app_database

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=test_engine, class_=AsyncSession
)


async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(scope="function", name="client")
async def client_fixture(monkeypatch) -> TestClient:
    monkeypatch.setattr(app_database, "engine", test_engine)

    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async def mock_check_polygon_options_access():
        return True

    app.dependency_overrides[get_db_session] = override_get_session
    app.dependency_overrides[check_polygon_options_access] = mock_check_polygon_options_access

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest.fixture
def mock_httpx():
    with respx.mock as mock:
        yield mock
