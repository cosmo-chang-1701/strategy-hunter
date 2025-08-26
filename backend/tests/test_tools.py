import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.asyncio


# Tests for the Position Size Calculator
async def test_calculate_position_size_normal(client: TestClient):
    request_data = {
        "total_capital": 25000,
        "risk_percentage": 2,
        "max_loss_per_contract": 250
    }
    response = client.post("/api/v1/tools/position-size", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["max_risk_amount"] == 500
    assert data["suggested_contracts"] == 2
    assert "建議的交易數量為 2 份合約" in data["message"]

async def test_calculate_position_size_high_risk(client: TestClient):
    request_data = {
        "total_capital": 25000,
        "risk_percentage": 2,
        "max_loss_per_contract": 600 # Higher than the max risk amount
    }
    response = client.post("/api/v1/tools/position-size", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["max_risk_amount"] == 500
    assert data["suggested_contracts"] == 0
    assert "不建議建立倉位" in data["message"]

async def test_calculate_position_size_invalid_loss_is_422(client: TestClient):
    """
    Test that sending a max_loss_per_contract of 0 is rejected by validation.
    """
    request_data = {
        "total_capital": 25000,
        "risk_percentage": 2,
        "max_loss_per_contract": 0
    }
    response = client.post("/api/v1/tools/position-size", json=request_data)
    assert response.status_code == 422


# Tests for the Tax Simulator
async def test_tax_simulator_below_threshold(client: TestClient):
    request_data = {
        "realized_capital_gains": 500000,
        "dividends": 100000
    }
    response = client.post("/api/v1/tools/tax-simulator", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["total_overseas_income"] == 600000
    assert not data["is_reporting_needed"]
    assert data["estimated_minimum_tax"] == 0
    assert "無需將其計入基本所得額申報" in data["summary"]

async def test_tax_simulator_above_threshold_no_tax(client: TestClient):
    request_data = {
        "realized_capital_gains": 2000000,
        "dividends": 1000000
    }
    response = client.post("/api/v1/tools/tax-simulator", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["total_overseas_income"] == 3000000
    assert data["is_reporting_needed"]
    assert data["estimated_minimum_tax"] == 0
    assert "無須繳納最低稅負" in data["summary"]

async def test_tax_simulator_with_tax(client: TestClient):
    request_data = {
        "realized_capital_gains": 8000000,
        "dividends": 2000000
    }
    response = client.post("/api/v1/tools/tax-simulator", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["total_overseas_income"] == 10000000
    assert data["is_reporting_needed"]
    assert data["taxable_basic_income"] == 2500000 # 10,000,000 - 7,500,000
    assert data["estimated_minimum_tax"] == 500000 # 2,500,000 * 0.20
    assert "預估產生的最低稅負為 NT$ 500,000" in data["summary"]
