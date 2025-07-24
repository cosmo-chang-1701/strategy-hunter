import os
import httpx # 匯入 httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from dotenv import load_dotenv # 匯入 dotenv

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

@app.get("/")
async def read_root():
    return {"message": "歡迎使用美股選擇權分析平台 API"}