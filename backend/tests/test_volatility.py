import pytest
import httpx
from fastapi.testclient import TestClient
from respx import MockRouter
from datetime import date, timedelta

from app.config import settings

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_volatility_apis(respx_mock: MockRouter):
    ticker = "AAPL"
    fmp_api_key = settings.FMP_API_KEY
    polygon_api_key = settings.POLYGON_API_KEY
    today = date.today()
    one_year_ago = today - timedelta(days=365)

    # Mock FMP API for Implied Volatility
    fmp_url = f"https://financialmodelingprep.com/api/v3/historical-daily-implied-volatility/{ticker}?from={one_year_ago}&to={today}&apikey={fmp_api_key}"
    respx_mock.get(fmp_url).mock(
        return_value=httpx.Response(
            200,
            json=[
                {"date": "2023-01-01", "impliedVolatility": 0.2},
                {"date": "2023-01-02", "impliedVolatility": 0.8},
                {"date": str(today), "impliedVolatility": 0.5},
            ],
        )
    )

    # Mock Polygon API for Historical Prices
    polygon_url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{one_year_ago}/{today}?adjusted=true&sort=asc&limit=5000"
    respx_mock.get(polygon_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"t": 1672531200000, "c": 130.0}, # 2023-01-01
                    {"t": 1672617600000, "c": 131.0}, # 2023-01-02
                    # Add enough data points for HV calculation
                    *([{"t": 1672704000000 + i*86400000, "c": 131.0+i} for i in range(30)])
                ]
            },
        )
    )
    return respx_mock


async def test_get_volatility_analysis_success(client: TestClient, mock_volatility_apis):
    response = client.get("/api/v1/stocks/AAPL/volatility")

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert data["current_iv"] == 0.5
    assert data["iv_52_week_high"] == 0.8
    assert data["iv_52_week_low"] == 0.2
    assert data["iv_rank"] == 50.0 # (0.5 - 0.2) / (0.8 - 0.2) * 100
    assert len(data["chart_data"]) > 0
    assert data["chart_data"][-1]["iv"] is None # HV calc padding makes dates misaligned


async def test_get_volatility_analysis_api_failure(client: TestClient, respx_mock: MockRouter):
    ticker = "FAIL"
    fmp_api_key = settings.FMP_API_KEY
    today = date.today()
    one_year_ago = today - timedelta(days=365)

    # Mock FMP API to fail
    fmp_url = f"https://financialmodelingprep.com/api/v3/historical-daily-implied-volatility/{ticker.upper()}?from={one_year_ago}&to={today}&apikey={fmp_api_key}"
    respx_mock.get(fmp_url).mock(return_value=httpx.Response(500))

    # Mock Polygon API to succeed (to ensure one failure is enough)
    polygon_url = f"https://api.polygon.io/v2/aggs/ticker/{ticker.upper()}/range/1/day/{one_year_ago}/{today}?adjusted=true&sort=asc&limit=5000"
    respx_mock.get(polygon_url).mock(return_value=httpx.Response(200, json={"results": []}))

    response = client.get(f"/api/v1/stocks/{ticker}/volatility")

    assert response.status_code == 503
    assert "Failed to fetch historical data" in response.json()["detail"]
