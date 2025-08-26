import pytest
import httpx
from fastapi.testclient import TestClient
from respx import MockRouter
from app.config import settings

pytestmark = pytest.mark.asyncio


async def test_get_market_overview_success(client: TestClient, mock_httpx: MockRouter):
    api_key = settings.FMP_API_KEY
    mock_url = f"https://financialmodelingprep.com/api/v3/quote/SPY,QQQ,DIA?apikey={api_key}"
    mock_httpx.get(mock_url).mock(
        return_value=httpx.Response(
            200,
            json=[
                {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "price": 450.5, "changesPercentage": 0.5, "change": 2.25},
                {"symbol": "QQQ", "name": "Invesco QQQ Trust", "price": 400.5, "changesPercentage": -0.2, "change": -0.8},
                {"symbol": "DIA", "name": "SPDR Dow Jones Industrial Average ETF", "price": 350.0, "changesPercentage": 0.1, "change": 0.35},
            ],
        )
    )

    response = client.get("/api/v1/market-overview")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["symbol"] == "SPY"
    assert data[1]["name"] == "Invesco QQQ Trust"


async def test_get_stock_quote_success(client: TestClient, mock_httpx: MockRouter):
    api_key = settings.FMP_API_KEY
    ticker = "AAPL"
    mock_url = f"https://financialmodelingprep.com/api/v3/quote/{ticker}?apikey={api_key}"
    mock_httpx.get(mock_url).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "price": 151.0,
                    "changesPercentage": 1.5,
                    "change": 2.25,
                    "dayLow": 149.0,
                    "dayHigh": 155.0,
                    "yearHigh": 180.0,
                    "yearLow": 120.0,
                    "marketCap": 2500000000000,
                    "priceAvg50": 145.0,
                    "priceAvg200": 140.0,
                    "volume": 1000000,
                    "avgVolume": 1200000,
                    "open": 152.0,
                    "previousClose": 148.75,
                    "exchange": "NASDAQ",
                }
            ],
        )
    )

    response = client.get(f"/api/v1/stocks/{ticker}/quote")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["price"] == 151.0


async def test_get_stock_quote_not_found(client: TestClient, mock_httpx: MockRouter):
    api_key = settings.FMP_API_KEY
    ticker = "UNKNOWN"
    mock_url = f"https://financialmodelingprep.com/api/v3/quote/{ticker}?apikey={api_key}"
    mock_httpx.get(mock_url).mock(return_value=httpx.Response(200, json=[]))

    response = client.get(f"/api/v1/stocks/{ticker}/quote")
    assert response.status_code == 404
    assert response.json() == {"detail": f"Stock with ticker '{ticker}' not found."}


async def test_get_market_overview_service_unavailable(client: TestClient, mock_httpx: MockRouter):
    api_key = settings.FMP_API_KEY
    mock_url = f"https://financialmodelingprep.com/api/v3/quote/SPY,QQQ,DIA?apikey={api_key}"
    mock_httpx.get(mock_url).mock(return_value=httpx.Response(500))

    response = client.get("/api/v1/market-overview")
    assert response.status_code == 503
    assert response.json() == {"detail": "Could not fetch market overview data."}
