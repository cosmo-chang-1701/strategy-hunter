import numpy as np
from typing import List, Dict, Any, Optional
import os
import asyncio
import httpx
from datetime import date, timedelta
from fastapi import HTTPException
from app.schemas import VolatilityAnalysis, VolatilityDataPoint


class VolatilityCalculatorService:
    async def get_volatility_analysis(self, ticker: str):
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
                raise HTTPException(
                    status_code=503, detail=f"Failed to fetch historical data: {e}"
                )

        # --- 數據處理與計算 ---
        # 處理 FMP 的 IV 數據
        iv_map = {item["date"]: item["impliedVolatility"] for item in fmp_data}

        # 處理 Polygon 的價格數據並計算 HV
        dates = [p["t"] / 1000 for p in polygon_data]  # Polygon timestamp is in ms
        prices = [p["c"] for p in polygon_data]
        hv_list = self.calculate_hv(prices)

        # 計算 IV 指標
        iv_indicators = self.calculate_iv_indicators(list(iv_map.values()))

        # --- 組合最終結果 ---
        chart_data = []
        for i, ts in enumerate(dates):
            current_date = date.fromtimestamp(ts)
            date_str = current_date.strftime("%Y-%m-%d")
            chart_data.append(
                VolatilityDataPoint(
                    date=current_date, iv=iv_map.get(date_str), hv=hv_list[i]
                )
            )

        return VolatilityAnalysis(
            ticker=ticker.upper(), chart_data=chart_data, **iv_indicators
        )

    def calculate_hv(
        self, prices: List[float], window: int = 30
    ) -> List[Optional[float]]:
        """
        計算歷史波動率 (HV)。
        :param prices: 每日收盤價列表。
        :param window: 計算波動率的滾動窗口天數，通常為30天。
        :return: 每日的年化歷史波動率列表。
        """
        if len(prices) < window:
            return []

        # 計算每日對數收益率
        log_returns = np.log(np.array(prices) / np.roll(np.array(prices), 1))

        # 計算對數收益率的滾動標準差
        # np.std 計算標準差，ddof=1 使用樣本標準差
        rolling_std = np.lib.stride_tricks.as_strided(
            log_returns,
            shape=(len(log_returns) - window + 1, window),
            strides=(log_returns.strides[0], log_returns.strides[0]),
        ).std(axis=1, ddof=1)

        # 年化波動率 (乘以 sqrt(252)，一年約有252個交易日)
        annualized_hv = rolling_std * np.sqrt(252)

        # 為了讓結果列表長度與輸入對齊，前面補上空值
        # 將 annualized_hv 轉換為 Python 的 list
        hv_list = annualized_hv.tolist()

        # 建立一個包含 None 的前綴
        padding = [None] * (len(prices) - len(hv_list))

        # 為了讓結果列表長度與輸入對齊，前面補上空值
        return padding + hv_list

    def calculate_iv_indicators(self, iv_series: List[float]) -> Dict[str, Any]:
        """
        計算 IV Rank 和 IV Percentile。
        :param iv_series: 每日隱含波動率列表 (過去52週)。
        :return: 包含各項指標的字典。
        """
        if not iv_series:
            return {}

        clean_iv_series = [iv for iv in iv_series if iv is not None]
        if not clean_iv_series:
            return {}

        current_iv = clean_iv_series[-1]
        high_52wk = max(clean_iv_series)
        low_52wk = min(clean_iv_series)

        # 計算 IV Rank
        ivr = (
            ((current_iv - low_52wk) / (high_52wk - low_52wk)) * 100
            if (high_52wk - low_52wk) > 0
            else 0
        )

        # 計算 IV Percentile
        ivp = (
            np.sum(np.array(clean_iv_series) < current_iv) / len(clean_iv_series)
        ) * 100

        return {
            "current_iv": current_iv,
            "iv_rank": round(ivr, 2),
            "iv_percentile": round(ivp, 2),
            "iv_52_week_high": high_52wk,
            "iv_52_week_low": low_52wk,
        }


def get_volatility_calculator_service() -> VolatilityCalculatorService:
    """依賴注入函數，提供 VolatilityCalculatorService 實例。"""
    return VolatilityCalculatorService()
