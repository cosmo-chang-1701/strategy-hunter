import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from dotenv import load_dotenv
import asyncio
from datetime import date, timedelta
from contextlib import asynccontextmanager

# --- 計算模組 ---
from volatility_calculator import calculate_hv, calculate_iv_indicators
from strategy_analyzer import analyze_strategy as perform_strategy_analysis, OptionLeg

# 在應用程式啟動時，載入 .env 檔案中的環境變數
load_dotenv()

# --- 應用程式狀態管理 ---
# 我們將使用一個簡單的字典來儲存應用程式的狀態，例如 API 的可用性
app_state = {}

# --- FastAPI 生命週期管理器 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("INFO:     Application startup...")
    print("INFO:     Performing Polygon.io v3 options access check...")
    app_state["polygon_options_accessible"] = await check_polygon_options_access()
    if app_state["polygon_options_accessible"]:
        print("INFO:     Polygon.io v3 options snapshot access: VERIFIED")
    else:
        print("WARNING:  Polygon.io v3 options snapshot access: FAILED. Option chain will use mock data.")
    yield
    print("INFO:     Application shutdown.")
    app_state.clear()


# 1. 建立 FastAPI 應用程式實例
app = FastAPI(
    title="美股選擇權分析平台 API",
    description="提供美股市場數據、選擇權鏈、策略分析等功能。",
    version="1.0.0",
    lifespan=lifespan
)

# 2. 定義數據模型
class MarketIndex(BaseModel):
    name: str
    symbol: str
    price: float
    change: float
    change_percent: float

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

class OptionContract(BaseModel):
    strike_price: float
    contract_type: str # "call" 或 "put"
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
    is_itm: bool # 是否為價內

class OptionChain(BaseModel):
    isMock: bool = False
    underlying_price: float
    calls: List[OptionContract]
    puts: List[OptionContract]

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

# OptionLeg is now imported from strategy_analyzer to ensure type consistency.

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

# 3. 建立 API 端點
# --- API 健康檢查函式 ---
async def check_polygon_options_access() -> bool:
    """
    在啟動時執行，檢查 Polygon API 金鑰是否能存取選擇權快照。
    返回 True 代表權限正常，False 代表權限不足或發生錯誤。
    """
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        return False

    # 我們用一個高流通性的 SPY ETF 及其選擇權作為測試對象
    # O:SPY250815C00550000 是一個 SPY 2025/08/15 到期，$550 的 Call
    test_tickers = "SPY,O:SPY250815C00550000"
    url = f"https://api.polygon.io/v3/snapshot?ticker.any_of={test_tickers}&apiKey={api_key}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code == 200:
                # 檢查回傳的 tickers 中是否真的包含我們的選擇權 ticker
                data = response.json()
                for item in data.get('results', []):
                    if item.get('ticker') == 'O:SPY250815C00550000' and not item.get('error'):
                        return True # 找到選擇權且沒有錯誤
            return False
    except Exception as e:
        print(f"ERROR during Polygon access check: {e}")
        return False

@app.get("/api/v1/market-overview", response_model=List[MarketIndex])
async def get_market_overview():
    """
    獲取美國三大市場指數的即時概覽。
    數據來源：Financial Modeling Prep API (使用 ETF 作為指數代表)
    """
    # 從環境變數讀取 API 金鑰
    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="FMP_API_KEY not found in environment variables.")

    # FMP API 使用的指數代碼
    # SPY = S&P 500 ETF, DIA = Dow Jones ETF, QQQ = Nasdaq 100 ETF
    index_symbols = "SPY,QQQ,DIA"
    url = f"https://financialmodelingprep.com/api/v3/quote/{index_symbols}?apikey={api_key}"

    # 使用 httpx 進行非同步 API 請求
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            # 如果 API 回應不是成功 (200 OK)，則拋出錯誤
            response.raise_for_status() 
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"Error while requesting from FMP API: {exc}")
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=f"FMP API returned an error: {exc.response.text}")

    # 解析 FMP 回傳的資料
    data_from_fmp = response.json()

    # 將 FMP 的資料格式轉換為我們自己的 MarketIndex 格式
    market_overview = []
    for index_data in data_from_fmp:
        market_overview.append(
            MarketIndex(
                name=index_data.get("name"),
                symbol=index_data.get("symbol"),
                price=index_data.get("price"),
                change=index_data.get("change"),
                # FMP 的 'changesPercentage' 對應到我們的 'change_percent'
                change_percent=index_data.get("changesPercentage")
            )
        )
        
    return market_overview

@app.get("/api/v1/stocks/{ticker}/quote", response_model=StockQuote)
async def get_stock_quote(ticker: str):
    """
    獲取指定股票的即時報價與基本數據。
    - **ticker**: 股票代碼 (例如: AAPL, TSLA)
    """
    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="FMP_API_KEY not found.")

    # FMP 的報價 API
    url = f"https://financialmodelingprep.com/api/v3/quote/{ticker.upper()}?apikey={api_key}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            # FMP API 即使查詢單一股票也可能回傳列表，且列表可能為空
            if not data:
                raise HTTPException(status_code=404, detail=f"Stock ticker '{ticker}' not found.")
            
            stock_data = data[0]

        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"Error while requesting from FMP API: {exc}")
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=f"FMP API returned an error: {exc.response.text}")

    # 將 FMP 回傳的資料轉換為我們的 StockQuote 格式
    return StockQuote(
        symbol=stock_data.get("symbol"),
        name=stock_data.get("name"),
        price=stock_data.get("price"),
        change=stock_data.get("change"),
        change_percent=stock_data.get("changesPercentage"),
        day_low=stock_data.get("dayLow"),
        day_high=stock_data.get("dayHigh"),
        year_low=stock_data.get("yearLow"),
        year_high=stock_data.get("yearHigh"),
        volume=stock_data.get("volume")
    )

@app.get("/api/v1/stocks/{ticker}/options/expirations", response_model=List[str])
async def get_option_expirations(ticker: str):
    """
    獲取指定股票所有可用的選擇權到期日列表。
    數據來源：Polygon.io
    """
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="POLYGON_API_KEY not found.")

    # Polygon.io 的選擇權合約查詢 API
    # 我們查詢所有合約並從中提取出不重複的到期日
    url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={ticker.upper()}&limit=1000&apiKey={api_key}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"Error requesting from Polygon API: {exc}")
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=f"Polygon API error: {exc.response.text}")
    
    # 從回傳的合約列表中，整理出所有不重複的到期日
    # 使用 set 可以自動去除重複的日期
    expirations = {contract["expiration_date"] for contract in data.get("results", [])}
    
    # 將 set 轉換為 list 並排序後回傳
    return sorted(list(expirations))

@app.get("/api/v1/stocks/{ticker}/options", response_model=OptionChain)
async def get_option_chain(ticker: str, expiration_date: str):
    """
    獲取指定股票和到期日的完整選擇權鏈，包含希臘值。
    - **ticker**: 股票代碼 (e.g., AAPL)
    - **expiration_date**: 選擇權到期日 (格式: YYYY-MM-DD)
    """
    # Mock data 模式
    if not app_state.get("polygon_options_accessible", False):
        print("INFO: Operating in 'mock' mode. Returning mock option chain data.")
        underlying_price = 215.50
        
        mock_calls = [
            OptionContract(
                strike_price=210.0, 
                contract_type='call', 
                bid=7.50, 
                ask=7.60, 
                last_price=7.55, 
                volume=150, 
                open_interest=1200, 
                implied_volatility=0.28, 
                delta=0.65, 
                gamma=0.05, 
                theta=-0.12, 
                vega=0.35, 
                is_itm=True
            ),
            OptionContract(
                strike_price=215.0, 
                contract_type='call', 
                bid=4.20, 
                ask=4.25, 
                last_price=4.22, 
                volume=350, 
                open_interest=2500, 
                implied_volatility=0.27, 
                delta=0.51, 
                gamma=0.07, 
                theta=-0.15, 
                vega=0.40, 
                is_itm=True
            ),
            OptionContract(
                strike_price=220.0, 
                contract_type='call', 
                bid=2.10, 
                ask=2.15, 
                last_price=2.13, 
                volume=280, 
                open_interest=1800, 
                implied_volatility=0.26, 
                delta=0.35, 
                gamma=0.06, 
                theta=-0.14, 
                vega=0.38, 
                is_itm=False
            ),
        ]
        
        mock_puts = [
            OptionContract(
                strike_price=210.0, 
                contract_type='put', 
                bid=2.80, 
                ask=2.85, 
                last_price=2.83, 
                volume=180, 
                open_interest=1500, 
                implied_volatility=0.28, 
                delta=-0.38, 
                gamma=0.06, 
                theta=-0.13, 
                vega=0.36, 
                is_itm=False
            ),
            OptionContract(
                strike_price=215.0, 
                contract_type='put', 
                bid=4.80, 
                ask=4.90, 
                last_price=4.85, 
                volume=320, 
                open_interest=2200, 
                implied_volatility=0.27, 
                delta=-0.49, 
                gamma=0.07, 
                theta=-0.15, 
                vega=0.40, 
                is_itm=False
            ),
            OptionContract(
                strike_price=220.0, 
                contract_type='put', 
                bid=7.90, 
                ask=8.00, 
                last_price=7.95, 
                volume=110, 
                open_interest=1100, 
                implied_volatility=0.26, 
                delta=-0.64, 
                gamma=0.05, 
                theta=-0.11, 
                vega=0.37, 
                is_itm=True
            ),
        ]
        
        return OptionChain(
            underlying_price=underlying_price, 
            calls=mock_calls, 
            puts=mock_puts, 
            isMock=True
        )

    # 正常模式：從 Polygon.io 獲取實際數據
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="POLYGON_API_KEY not found.")

    # --- 步驟 1: 獲取該到期日的所有選擇權合約代碼 ---
    contracts_url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={ticker.upper()}&expiration_date={expiration_date}&limit=1000&apiKey={api_key}"
    async with httpx.AsyncClient() as client:
        contracts_res = await client.get(contracts_url)
        contracts_data = contracts_res.json().get("results", [])
        option_tickers = [c["ticker"] for c in contracts_data]
    if not option_tickers:
        return OptionChain(underlying_price=0, calls=[], puts=[])

    # --- 步驟 2: 批量獲取所有合約 + 股票本身的市場快照 ---
    # 將股票本身的 ticker 也加入查詢列表
    all_tickers_to_query = option_tickers + [ticker.upper()]
    BATCH_SIZE = 25
    snapshot_map = {}

    async with httpx.AsyncClient() as client:
        tasks = []
        for i in range(0, len(all_tickers_to_query), BATCH_SIZE):
            batch = all_tickers_to_query[i:i + BATCH_SIZE]
            tickers_str = ",".join(batch)
            url = f"https://api.polygon.io/v3/snapshot?ticker.any_of={tickers_str}&apiKey={api_key}"
            tasks.append(client.get(url))
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        for res in responses:
            if isinstance(res, Exception):
                continue
            if isinstance(res, httpx.Response) and res.status_code == 200:
                for item in res.json().get("results", []):
                    if not item.get("error"):
                        snapshot_map[item["ticker"]] = item

    # --- 步驟 3: 從快照中提取股價並組合數據 ---
    stock_snapshot = snapshot_map.get(ticker.upper())

    if not stock_snapshot:
        raise HTTPException(
            status_code=404, 
            detail=f"Could not fetch snapshot for stock '{ticker.upper()}'."
        )
    
    underlying_price = (
        stock_snapshot.get('session', {}).get('close') or 
        stock_snapshot.get('last_trade', {}).get('price')
    )
    
    if underlying_price is None:
        raise HTTPException(
            status_code=404, 
            detail=f"Could not parse price from stock snapshot: {stock_snapshot}"
        )

    # --- 步驟 4: 組合數據---
    calls, puts = [], []
    for contract in contracts_data:
        snap = snapshot_map.get(contract["ticker"])
        if not snap or not snap.get("greeks"):
            continue
        
        details = snap['details']
        is_itm = (
            (details['contract_type'] == 'call' and details['strike_price'] < underlying_price) or
            (details['contract_type'] == 'put' and details['strike_price'] > underlying_price)
        )
        
        contract_obj = OptionContract(
            strike_price=details['strike_price'], 
            contract_type=details['contract_type'],
            bid=snap['last_quote']['bid'], 
            ask=snap['last_quote']['ask'],
            last_price=snap.get('last_trade', {}).get('price'),
            volume=snap.get('session', {}).get('volume'),
            open_interest=snap.get('open_interest'),
            implied_volatility=snap.get('implied_volatility'),
            delta=snap['greeks']['delta'], 
            gamma=snap['greeks']['gamma'],
            theta=snap['greeks']['theta'], 
            vega=snap['greeks']['vega'],
            is_itm=is_itm
        )

        if details['contract_type'] == 'call':
            calls.append(contract_obj)
        else:
            puts.append(contract_obj)

    calls.sort(key=lambda c: c.strike_price)
    puts.sort(key=lambda c: c.strike_price)
    
    return OptionChain(
        underlying_price=underlying_price, 
        calls=calls, 
        puts=puts
    )

@app.get("/api/v1/stocks/{ticker}/volatility", response_model=VolatilityAnalysis)
async def get_volatility_analysis(ticker: str):
    """
    獲取指定股票的波動率分析數據，包含 IV/HV 歷史圖表數據及 IV Rank/Percentile。
    """
    fmp_api_key = os.getenv("FMP_API_KEY")
    polygon_api_key = os.getenv("POLYGON_API_KEY")
    if not fmp_api_key or not polygon_api_key:
        raise HTTPException(status_code=500, detail="API keys are missing.")

    today = date.today()
    one_year_ago = today - timedelta(days=365)

    async with httpx.AsyncClient() as client:
        # --- 併發執行兩個 API 請求 ---
        # 任務1: 從 FMP 獲取歷史 IV
        fmp_url = f"https://financialmodelingprep.com/api/v3/historical-daily-implied-volatility/{ticker.upper()}?from={one_year_ago}&to={today}&apikey={fmp_api_key}"
        # 任務2: 從 Polygon 獲取歷史股價 (用於計算 HV)
        polygon_url = f"https://api.polygon.io/v2/aggs/ticker/{ticker.upper()}/range/1/day/{one_year_ago}/{today}?adjusted=true&sort=asc&limit=5000&apiKey={polygon_api_key}"
        
        try:
            fmp_task = client.get(fmp_url)
            polygon_task = client.get(polygon_url)
            responses = await asyncio.gather(fmp_task, polygon_task)
            
            fmp_res, polygon_res = responses
            fmp_res.raise_for_status()
            polygon_res.raise_for_status()
            
            fmp_json = fmp_res.json()
            if isinstance(fmp_json, list):
                fmp_data = fmp_json
            else:
                # 如果 FMP 回傳錯誤訊息 (通常是字典)，則視為空數據
                fmp_data = []

            polygon_data = polygon_res.json().get("results", [])

        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Failed to fetch historical data: {e}")

    # --- 數據處理與計算 ---
    # 處理 FMP 的 IV 數據
    iv_map = {item['date']: item['impliedVolatility'] for item in fmp_data}
    
    # 處理 Polygon 的價格數據並計算 HV
    dates = [p['t'] / 1000 for p in polygon_data] # Polygon timestamp is in ms
    prices = [p['c'] for p in polygon_data]
    hv_list = calculate_hv(prices)
    
    # 計算 IV 指標
    iv_indicators = calculate_iv_indicators(list(iv_map.values()))

    # --- 組合最終結果 ---
    chart_data = []
    for i, ts in enumerate(dates):
        current_date = date.fromtimestamp(ts)
        date_str = current_date.strftime('%Y-%m-%d')
        chart_data.append(
            VolatilityDataPoint(
                date=current_date,
                iv=iv_map.get(date_str),
                hv=hv_list[i]
            )
        )
    
    return VolatilityAnalysis(
        ticker=ticker.upper(),
        chart_data=chart_data,
        **iv_indicators
    )

@app.post("/api/v1/strategies/analyze", response_model=AnalyzedStrategy)
async def analyze_strategy_endpoint(strategy: StrategyDefinition):
    """
    接收一個策略定義，並回傳完整的量化分析結果。
    - **Request Body**: 一個包含 'legs' 列表的 JSON 物件。
    """
    try:
        analysis_result = await perform_strategy_analysis(strategy.legs)
        return analysis_result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

@app.get("/")
async def read_root():
    return {"message": "歡迎使用美股選擇權分析平台 API"}