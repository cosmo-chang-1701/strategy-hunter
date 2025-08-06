from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from .. import schemas
from ..services import strategy_service

router = APIRouter(prefix="/api/v1/strategies", tags=["Strategies"])


@router.post(
    "/find",
    response_model=List[schemas.RecommendedStrategy],
    summary="尋找推薦的期權策略",
)
async def find_strategies(
    strategies: List[schemas.RecommendedStrategy] = Depends(
        strategy_service.find_strategies_by_criteria
    ),
):
    """
    根據市場方向和波動率預期，尋找推薦的期權策略。
    """
    return strategies


@router.post(
    "/analyze", response_model=schemas.AnalyzedStrategy, summary="分析策略表現"
)
async def analyze_strategy_endpoint(
    analysis_result: Dict[str, Any] = Depends(
        strategy_service.analyze_strategy_performance
    ),
):
    """
    分析給定策略的損益情況、最大風險、最大回報和希臘值。
    """
    if "error" in analysis_result:
        status_code = analysis_result.get("status_code", 400)
        raise HTTPException(status_code=status_code, detail=analysis_result["error"])
    return analysis_result
