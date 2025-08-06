import httpx
from typing import List
from .. import schemas
from ..config import settings


class MarketDataService:
    async def fetch_market_overview(self) -> List[schemas.MarketIndex]:
        """從 FMP 獲取市場指數概覽 (ETF代表)。"""
        api_key = settings.FMP_API_KEY
        index_symbols = "SPY,QQQ,DIA"
        url = f"https://financialmodelingprep.com/api/v3/quote/{index_symbols}?apikey={api_key}"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                return [schemas.MarketIndex.from_fmp_data(item) for item in data]
            except httpx.HTTPError as e:
                # 在服務層可以記錄錯誤，但讓路由層決定 HTTP 響應
                # 或者拋出一個自定義的服務層異常
                # 此處為了簡化，我們回傳空列表，由路由層處理
                print(f"Error fetching market overview from FMP API: {e}")
                return []

    async def fetch_stock_quote(self, ticker: str) -> schemas.StockQuote | None:
        """從 FMP 獲取單一股票的報價。"""
        api_key = settings.FMP_API_KEY
        url = f"https://financialmodelingprep.com/api/v3/quote/{ticker.upper()}?apikey={api_key}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                if not data:
                    return None
                # 將 FMP 的資料格式轉換為我們的 StockQuote 格式
                return schemas.StockQuote.from_fmp_data(data[0])
            except httpx.HTTPError as e:
                print(f"Error fetching stock quote from FMP API: {e}")
                return None


def get_market_data_service() -> MarketDataService:
    """依賴注入函數，提供 MarketDataService 實例。"""
    return MarketDataService()
