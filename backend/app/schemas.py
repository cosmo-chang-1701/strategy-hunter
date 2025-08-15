from pydantic import BaseModel, Field
from enum import Enum
from datetime import date
from typing import List, Optional

# =============================================================================
# Enums - 列舉類型
# =============================================================================


class MarketDirection(str, Enum):
    STRONG_BULLISH = "大漲"
    MILD_BULLISH = "溫和看漲"
    NEUTRAL = "盤整"
    MILD_BEARISH = "溫和看跌"
    STRONG_BEARISH = "大跌"


class VolatilityDirection(str, Enum):
    RISING = "IV上升"
    NEUTRAL = "IV持平"
    FALLING = "IV下降"


# =============================================================================
# Market Data - 市場數據相關模型
# =============================================================================


class MarketIndex(BaseModel):
    name: str
    symbol: str
    price: float
    change: float
    change_percent: float

    class Config:
        from_attributes = True

    @classmethod
    def from_fmp_data(cls, data: dict):
        """從 FMP API 的資料創建 MarketIndex 實例。"""
        return cls(
            name=data.get("name") or "N/A",
            symbol=data.get("symbol") or "N/A",
            price=data.get("price") or 0.0,
            change=data.get("change") or 0.0,
            change_percent=data.get("changesPercentage") or 0.0,
        )


class StockQuote(BaseModel):
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    day_low: float
    day_high: float
    year_low: float
    year_high: float
    volume: int
    market_cap: int
    exchange: str

    class Config:
        from_attributes = True

    @classmethod
    def from_fmp_data(cls, data: dict):
        """從 FMP API 的資料創建 StockQuote 實例。"""
        return cls(
            symbol=data.get("symbol") or "N/A",
            name=data.get("name") or "N/A",
            price=data.get("price") or 0.0,
            change=data.get("change") or 0.0,
            change_percent=data.get("changesPercentage") or 0.0,
            day_low=data.get("dayLow") or 0.0,
            day_high=data.get("dayHigh") or 0.0,
            year_high=data.get("yearHigh") or 0.0,
            year_low=data.get("yearLow") or 0.0,
            volume=data.get("volume") or 0,
            market_cap=data.get("marketCap") or 0,
            exchange=data.get("exchange") or "N/A",
        )


# =============================================================================
# Volatility Analysis - 波動率分析相關模型
# =============================================================================


class VolatilityDataPoint(BaseModel):
    date: date
    iv: Optional[float] = None
    hv: Optional[float] = None


class VolatilityAnalysis(BaseModel):
    ticker: str
    current_iv: Optional[float] = None
    iv_rank: Optional[float] = None
    iv_percentile: Optional[float] = None
    iv_52_week_high: Optional[float] = None
    iv_52_week_low: Optional[float] = None
    chart_data: List[VolatilityDataPoint]


# =============================================================================
# Options - 選擇權相關模型
# =============================================================================


class OptionContract(BaseModel):
    symbol: str
    strike_price: float
    contract_type: str  # "call" 或 "put"
    bid: float
    ask: float
    last_price: Optional[float] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = None
    implied_volatility: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    is_itm: bool  # 是否為價內


class OptionChain(BaseModel):
    isMock: bool = False
    underlying_price: float
    calls: List[OptionContract]
    puts: List[OptionContract]


class OptionLeg(BaseModel):
    option_ticker: str
    action: str  # "BUY" or "SELL"
    quantity: int


# =============================================================================
# Strategy Finder - 策略推薦相關模型
# =============================================================================


class StrategyFinderRequest(BaseModel):
    direction: MarketDirection = Field(..., description="市場方向預期")
    volatility: VolatilityDirection = Field(..., description="波動率預期")


class RecommendedStrategy(BaseModel):
    name: str
    description: str
    risk_profile: str
    categories: List[str]


# =============================================================================
# Strategy Analysis - 策略分析相關模型
# =============================================================================


class StrategyDefinition(BaseModel):
    legs: List[OptionLeg]


class PLDataPoint(BaseModel):
    price_at_expiration: float
    profit_loss: float


class AnalyzedStrategy(BaseModel):
    max_profit: Optional[float]
    max_loss: Optional[float]
    breakeven_points: List[float]
    net_cost: float
    position_delta: float
    position_gamma: float
    position_theta: float
    position_vega: float
    pl_chart_data: List[PLDataPoint]
