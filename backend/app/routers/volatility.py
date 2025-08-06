from fastapi import APIRouter, HTTPException, Depends
from typing import List
from .. import schemas
from ..services import volatility_calculator_service

router = APIRouter(
    tags=["Volatility Analysis"],
)


@router.get(
    "/api/v1/stocks/{ticker}/volatility",
    response_model=schemas.VolatilityAnalysis,
    summary="獲取股票波動率分析",
)
async def get_volatility_analysis(
    ticker: str,
    service: volatility_calculator_service.VolatilityCalculatorService = Depends(
        volatility_calculator_service.get_volatility_calculator_service
    ),
) -> schemas.VolatilityAnalysis:
    """
    獲取指定股票的波動率分析數據，包含 IV/HV 歷史圖表數據及 IV Rank/Percentile。
    """
    try:
        return await service.get_volatility_analysis(ticker)
    except HTTPException as e:
        # 直接轉發 HTTP 異常
        raise e
    except Exception as e:
        # 捕獲任何其他意外錯誤
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred in volatility analysis: {e}",
        )
