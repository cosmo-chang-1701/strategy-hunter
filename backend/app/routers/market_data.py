from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from .. import schemas
from ..services import market_data_service

router = APIRouter(prefix="/api/v1", tags=["Market Data"])


@router.get(
    "/market-overview",
    response_model=List[schemas.MarketIndex],
    summary="獲取市場指數概覽",
)
async def get_market_overview(
    service: market_data_service.MarketDataService = Depends(
        market_data_service.get_market_data_service
    ),
):
    """
    獲取市場指數概覽。
    """
    overview_data = await service.fetch_market_overview()
    if not overview_data:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not fetch market overview data.",
        )
    return overview_data


@router.get(
    "/stocks/{ticker}/quote",
    response_model=schemas.StockQuote,
    summary="獲取股票即時報價",
)
async def get_stock_quote(
    ticker: str,
    service: market_data_service.MarketDataService = Depends(
        market_data_service.get_market_data_service
    ),
):
    """
    根據股票代碼獲取即時報價。
    """
    stock_data = await service.fetch_stock_quote(ticker)
    if not stock_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock with ticker '{ticker}' not found.",
        )
    return stock_data
