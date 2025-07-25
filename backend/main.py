import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv
import asyncio
from datetime import date, timedelta
from volatility_calculator import calculate_hv, calculate_iv_indicators

# 在應用程式啟動時，載入 .env 檔案中的環境變數
load_dotenv()

# 1. 建立 FastAPI 應用程式實例
app = FastAPI(
    title="美股選擇權分析平台 API",
    description="提供美股市場數據、選擇權鏈、策略分析等功能。",
    version="1.0.0",
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

# 3. 建立 API 端點
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
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="POLYGON_API_KEY not found.")

    # --- 步驟 1: 獲取該到期日的所有選擇權合約代碼 ---
    contracts_url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={ticker.upper()}&expiration_date={expiration_date}&limit=1000&apiKey={api_key}"
    async with httpx.AsyncClient() as client:
        try:
            contracts_res = await client.get(contracts_url)
            contracts_res.raise_for_status()
            contracts_data = contracts_res.json().get("results", [])
            option_tickers = [contract["ticker"] for contract in contracts_data]
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            raise HTTPException(status_code=503, detail=f"Failed to fetch options contracts from Polygon: {exc}")
            
    if not contracts_data:
        # 如果沒有任何合約，可能無法取得股價，直接回傳空值
        return OptionChain(underlying_price=0, calls=[], puts=[])

    # --- 步驟 2: 批量獲取所有合約 + 股票本身的市場快照 ---
    # 將股票本身的 ticker 也加入查詢列表
    all_tickers_to_query = option_tickers + [ticker.upper()]
    tickers_string = ",".join(all_tickers_to_query)
    snapshot_url = f"https://api.polygon.io/v2/snapshot/tickers?tickers={tickers_string}&apiKey={api_key}"
    
    async with httpx.AsyncClient() as client:
        try:
            snapshot_res = await client.get(snapshot_url)
            snapshot_res.raise_for_status()
            snapshot_data = snapshot_res.json().get("tickers", [])
            snapshot_map = {snap["ticker"]: snap for snap in snapshot_data}
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
             raise HTTPException(status_code=503, detail=f"Failed to fetch options snapshots from Polygon: {exc}")

    # --- 步驟 3: 從快照中提取股價並組合數據 ---
    stock_snapshot = snapshot_map.get(ticker.upper())
    if not stock_snapshot or stock_snapshot.get("lastTrade") is None:
        raise HTTPException(status_code=404, detail="Could not fetch underlying stock price from snapshot.")
    
    underlying_price = stock_snapshot["lastTrade"]["p"] # 使用最後成交價

    calls, puts = [], []
    for contract_info in contracts_data:
        ticker_symbol = contract_info["ticker"]
        snapshot = snapshot_map.get(ticker_symbol)
        
        if not snapshot or not snapshot.get("greeks"):
            continue

        strike = contract_info["strike_price"]
        contract_type = contract_info["contract_type"]
        is_itm = (contract_type == "call" and strike < underlying_price) or \
                 (contract_type == "put" and strike > underlying_price)

        option_contract = OptionContract(
            strike_price=strike,
            contract_type=contract_type,
            bid=snapshot["last_quote"]["bid"],
            ask=snapshot["last_quote"]["ask"],
            last_price=snapshot.get("day", {}).get("last"),
            volume=snapshot.get("day", {}).get("volume"),
            open_interest=snapshot.get("open_interest"),
            implied_volatility=snapshot.get("implied_volatility"),
            delta=snapshot["greeks"]["delta"],
            gamma=snapshot["greeks"]["gamma"],
            theta=snapshot["greeks"]["theta"],
            vega=snapshot["greeks"]["vega"],
            is_itm=is_itm
        )
        if contract_type == "call":
            calls.append(option_contract)
        else:
            puts.append(option_contract)

    calls.sort(key=lambda c: c.strike_price)
    puts.sort(key=lambda c: c.strike_price)

    return OptionChain(underlying_price=underlying_price, calls=calls, puts=puts)

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

@app.get("/")
async def read_root():
    return {"message": "歡迎使用美股選擇權分析平台 API"}