import pytest
import pytest_asyncio
import httpx
from fastapi.testclient import TestClient
from respx import MockRouter

from app.config import settings
from app.dependencies import get_option_chain_service
from app.services.option_chain_service import OptionChainService
from app.main import app

pytestmark = pytest.mark.asyncio

@pytest_asyncio.fixture(name="options_client")
async def options_client_fixture(client: TestClient):
    """A client fixture that overrides the option chain service to be 'live'."""
    def get_live_option_chain_service():
        return OptionChainService(is_live=True)

    original_override = app.dependency_overrides.get(get_option_chain_service)
    app.dependency_overrides[get_option_chain_service] = get_live_option_chain_service

    yield client

    # Restore original override or remove
    if original_override:
        app.dependency_overrides[get_option_chain_service] = original_override
    else:
        if get_option_chain_service in app.dependency_overrides:
            del app.dependency_overrides[get_option_chain_service]


async def test_get_option_expirations(options_client: TestClient, mock_httpx: MockRouter):
    ticker = "AAPL"
    api_key = settings.POLYGON_API_KEY
    mock_url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={ticker}&limit=1000"

    mock_httpx.get(mock_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"expiration_date": "2024-09-20"},
                    {"expiration_date": "2024-10-18"},
                ],
                "next_url": None,
            },
        )
    )

    response = options_client.get(f"/api/v1/stocks/{ticker}/options/expirations")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert "2024-09-20" in data
    assert "2024-10-18" in data


async def test_get_option_chain_success(options_client: TestClient, mock_httpx: MockRouter):
    ticker = "AAPL"
    expiration = "2024-09-20"
    api_key = settings.POLYGON_API_KEY

    # Mock for fetching underlying price
    price_url = f"https://api.polygon.io/v2/last/trade/{ticker}"
    mock_httpx.get(price_url).mock(
        return_value=httpx.Response(200, json={"results": {"p": 150.0}})
    )

    # Mock for fetching option chain
    chain_url = f"https://api.polygon.io/v3/snapshot/options/{ticker}?expiration_date={expiration}&limit=1000"
    mock_httpx.get(chain_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "details": {"ticker": "O:AAPL240920C00150000", "strike_price": 150.0, "contract_type": "call", "volume": 100, "open_interest": 1000},
                        "greeks": {"delta": 0.5, "gamma": 0.1, "theta": -0.1, "vega": 0.2},
                        "last_trade": {"price": 5.0},
                        "quote": {"bid": 4.9, "ask": 5.1},
                        "in_the_money": True,
                    }
                ]
            },
        )
    )

    response = options_client.get(f"/api/v1/stocks/{ticker}/options?expiration_date={expiration}")
    assert response.status_code == 200
    data = response.json()
    assert data["underlying_price"] == 150.0
    assert not data["isMock"]
    assert len(data["calls"]) == 1
    assert data["calls"][0]["strike_price"] == 150.0


async def test_get_option_chain_price_fetch_fails(options_client: TestClient, mock_httpx: MockRouter):
    ticker = "FAIL"
    expiration = "2024-09-20"

    # Mock for fetching underlying price to fail
    price_url = f"https://api.polygon.io/v2/last/trade/{ticker}"
    mock_httpx.get(price_url).mock(return_value=httpx.Response(500))

    response = options_client.get(f"/api/v1/stocks/{ticker}/options?expiration_date={expiration}")
    assert response.status_code == 500
    assert response.json() == {"detail": f"Could not fetch underlying price for {ticker}."}
