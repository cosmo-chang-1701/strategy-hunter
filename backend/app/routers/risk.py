from fastapi import APIRouter, Depends
from ..schemas import PositionSizeRequest, PositionSizeResponse
from ..services import risk_management_service

router = APIRouter(
    prefix="/api/v1/risk",
    tags=["Risk Management"],
)


@router.post(
    "/position-size",
    response_model=PositionSizeResponse,
    summary="計算建議的倉位規模",
)
def get_position_size(request: PositionSizeRequest):
    """
    根據總資金、風險百分比和策略最大虧損，計算建議的倉位規模。
    """
    return risk_management_service.calculate_position_size(request)
