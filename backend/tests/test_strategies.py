import pytest
import httpx
from fastapi.testclient import TestClient
from respx import MockRouter

from app.config import settings

pytestmark = pytest.mark.asyncio


async def test_find_strategies():
    from app.services.strategy_service import find_strategies_by_criteria
    from app.schemas import StrategyFinderRequest, MarketDirection, VolatilityDirection

    # Test case 1: Bullish and IV rising -> Should find Long Call and Long Straddle
    request = StrategyFinderRequest(
        direction=MarketDirection.STRONG_BULLISH,
        volatility=VolatilityDirection.RISING
    )
    results = find_strategies_by_criteria(request)
    result_names = {r.name for r in results}
    assert "Long Call (買入看漲期權)" in result_names
    assert "Long Straddle (買入跨式)" in result_names
    assert "Short Put (賣出看跌期權)" not in result_names

    # Test case 2: Neutral and IV falling -> Should find Iron Condor, Short Strangle, etc.
    request = StrategyFinderRequest(
        direction=MarketDirection.NEUTRAL,
        volatility=VolatilityDirection.FALLING
    )
    results = find_strategies_by_criteria(request)
    result_names = {r.name for r in results}
    assert "Iron Condor (鐵兀鷹)" in result_names
    assert "Short Strangle (賣出勒式)" in result_names
    assert "Long Call (買入看漲期權)" not in result_names

async def test_analyze_strategy_success(client: TestClient, mock_httpx: MockRouter):
    # Define a simple long call strategy
    strategy_definition = {
        "legs": [
            {
                "option_ticker": "O:SPY240920C00500000",
                "action": "BUY",
                "quantity": 1
            }
        ]
    }

    # Mock the polygon snapshot API call
    api_key = settings.POLYGON_API_KEY
    tickers_str = "O:SPY240920C00500000,SPY"
    mock_url = f"https://api.polygon.io/v3/snapshot?ticker.any_of={tickers_str}"

    mock_httpx.get(mock_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "ticker": "O:SPY240920C00500000",
                        "details": {"strike_price": 500.0, "contract_type": "call"},
                        "greeks": {"delta": 0.5, "gamma": 0.02, "theta": -0.05, "vega": 0.1},
                        "last_quote": {"bid": 10.0, "ask": 10.2},
                    },
                    {
                        "ticker": "SPY",
                        "session": {"close": 495.0}
                    }
                ]
            }
        )
    )

    response = client.post("/api/v1/strategies/analyze", json=strategy_definition)

    assert response.status_code == 200
    data = response.json()
    assert data["net_cost"] == 1010.0 # (10.0 + 10.2) / 2 * 1 * 100
    assert data["position_delta"] == 0.5
    assert len(data["pl_chart_data"]) > 0


async def test_analyze_strategy_api_error(client: TestClient, mock_httpx: MockRouter):
    strategy_definition = {
        "legs": [{"option_ticker": "O:ANYTICKER", "action": "BUY", "quantity": 1}]
    }

    api_key = settings.POLYGON_API_KEY
    tickers_str = "O:ANYTICKER,ANYTIC"
    mock_url = f"https://api.polygon.io/v3/snapshot?ticker.any_of={tickers_str}"

    # Mock a 404 response from the external API
    mock_httpx.get(mock_url).mock(
        return_value=httpx.Response(404, text="Not Found")
    )

    response = client.post("/api/v1/strategies/analyze", json=strategy_definition)
    assert response.status_code == 404
    assert "HTTP error occurred" in response.json()["detail"]
