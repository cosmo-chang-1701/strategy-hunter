import math
from fastapi import APIRouter
from pydantic import BaseModel, Field

# 為了讓此 router 獨立，我們在此處也定義它所需的模型
# 在大型專案中，這些模型也可以放在一個共用的地方


# --- 倉位規模計算機模型 ---
class PositionSizeRequest(BaseModel):
    total_capital: float = Field(..., gt=0, description="總資金")
    risk_percentage: float = Field(
        ..., gt=0, le=100, description="單筆交易風險容忍度 (%)"
    )
    max_loss_per_contract: float = Field(
        ..., gt=0, description="單份合約的最大虧損金額"
    )


class PositionSizeResponse(BaseModel):
    max_risk_amount: float
    suggested_contracts: int
    message: str


# --- 稅務模擬器模型 ---
class TaxSimulatorRequest(BaseModel):
    realized_capital_gains: float = Field(
        ..., ge=0, description="年度已實現海外資本利得 (台幣)"
    )
    dividends: float = Field(..., ge=0, description="年度已收取海外股息 (台幣)")


class TaxSimulatorResponse(BaseModel):
    total_overseas_income: float
    reporting_threshold: float
    is_reporting_needed: bool
    basic_income_deductible: float
    taxable_basic_income: float
    tax_rate_percentage: float
    estimated_minimum_tax: float
    summary: str
    disclaimer: str


# --- 路由設定 ---
router = APIRouter(prefix="/api/v1/tools", tags=["Tools & Calculators"])

# --- 稅務規則常數 (方便未來根據法規修改) ---
REPORTING_THRESHOLD = 1_000_000  # 海外所得申報門檻
BASIC_INCOME_DEDUCTIBLE = 7_500_000  # 基本所得額免稅額 (此數字可能變動)
MINIMUM_TAX_RATE = 0.20  # 最低稅負制稅率 20%


@router.post("/tax-simulator", response_model=TaxSimulatorResponse)
def simulate_overseas_income_tax(request: TaxSimulatorRequest):
    """
    模擬計算台灣投資者的海外所得最低稅負。
    注意：本模擬僅供參考，不構成稅務建議。
    """
    total_overseas_income = request.realized_capital_gains + request.dividends

    # 1. 判斷是否需要申報
    is_reporting_needed = total_overseas_income >= REPORTING_THRESHOLD

    # 2. 計算基本所得額 (此處簡化為僅考慮海外所得)
    # 在真實情況下，基本所得額 = 綜合所得淨額 + 海外所得 + ...
    basic_income_amount = total_overseas_income

    # 3. 計算應稅所得額
    taxable_basic_income = max(0, basic_income_amount - BASIC_INCOME_DEDUCTIBLE)

    # 4. 計算預估最低稅負
    estimated_minimum_tax = taxable_basic_income * MINIMUM_TAX_RATE

    # 5. 產生摘要訊息
    summary = f"您的年度海外所得總額為 NT$ {total_overseas_income:,.0f}。"
    if not is_reporting_needed:
        summary += f" 由於未達 NT$ {REPORTING_THRESHOLD:,.0f} 的申報門檻，您無需將其計入基本所得額申報。"
    else:
        summary += f" 已達申報門檻，應計入基本所得額。您的基本所得額（簡化模型）為 NT$ {basic_income_amount:,.0f}。"
        if estimated_minimum_tax > 0:
            summary += f" 扣除免稅額 NT$ {BASIC_INCOME_DEDUCTIBLE:,.0f} 後，您的應稅所得額為 NT$ {taxable_basic_income:,.0f}，預估產生的最低稅負為 NT$ {estimated_minimum_tax:,.0f}。"
        else:
            summary += f" 由於您的基本所得額未超過免稅額 NT$ {BASIC_INCOME_DEDUCTIBLE:,.0f}，在此模型下無須繳納最低稅負。"

    summary += " 最終應繳稅額需與您的「一般所得稅額」比較，取其高者繳納。"

    return TaxSimulatorResponse(
        total_overseas_income=total_overseas_income,
        reporting_threshold=REPORTING_THRESHOLD,
        is_reporting_needed=is_reporting_needed,
        basic_income_deductible=BASIC_INCOME_DEDUCTIBLE,
        taxable_basic_income=taxable_basic_income,
        tax_rate_percentage=MINIMUM_TAX_RATE * 100,
        estimated_minimum_tax=estimated_minimum_tax,
        summary=summary,
        disclaimer="本結果為根據簡化模型之模擬，僅供參考，不構成任何稅務建議。實際申報請諮詢專業會計師。",
    )


@router.post(
    "/position-size",
    response_model=PositionSizeResponse,
    summary="計算建議的倉位規模",
)
def calculate_position_size(request: PositionSizeRequest):
    """
    根據總資金、風險百分比和策略最大虧損，計算建議的倉位規模。
    """
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
