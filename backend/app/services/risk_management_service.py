import math
from ..schemas import PositionSizeRequest, PositionSizeResponse


def calculate_position_size(request: PositionSizeRequest) -> PositionSizeResponse:
    """
    根據總資金、風險百分比和策略最大虧損，計算建議的倉位規模。
    """
    # 1. 計算本次交易可承受的最大風險金額
    # 例如: $25,000 * (2 / 100) = $500
    max_risk_amount = request.total_capital * (request.risk_percentage / 100.0)

    # 2. 計算建議的合約數量
    # 例如: $500 / $250 (每份合約最大虧損) = 2 份
    # 使用 math.floor() 無條件捨去，以採取更保守的風險管理
    if request.max_loss_per_contract <= 0:
        suggested_contracts = 0
    else:
        suggested_contracts = math.floor(
            max_risk_amount / request.max_loss_per_contract
        )

    # 確保至少為 0，避免負數
    suggested_contracts = max(0, suggested_contracts)

    message = f"在總資金 ${request.total_capital:,.2f} 下，單筆交易承受 {request.risk_percentage}% 的風險，最多可虧損 ${max_risk_amount:,.2f}。"
    if suggested_contracts > 0:
        message += f" 建議的交易數量為 {suggested_contracts} 份合約。"
    else:
        message += " 該筆交易的潛在虧損過高，不建議建立倉位。"

    return PositionSizeResponse(
        max_risk_amount=round(max_risk_amount, 2),
        suggested_contracts=suggested_contracts,
        message=message,
    )
