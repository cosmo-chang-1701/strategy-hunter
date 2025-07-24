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

@app.get("/")
async def read_root():
    return {"message": "歡迎使用美股選擇權分析平台 API"}