import numpy as np
from typing import List, Dict, Any

def calculate_hv(prices: List[float], window: int = 30) -> List[float]:
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
        strides=(log_returns.strides[0], log_returns.strides[0])
    ).std(axis=1, ddof=1)

    # 年化波動率 (乘以 sqrt(252)，一年約有252個交易日)
    annualized_hv = rolling_std * np.sqrt(252)
    
    # 為了讓結果列表長度與輸入對齊，前面補上空值
    return [None] * (window - 1) + list(annualized_hv)


def calculate_iv_indicators(iv_series: List[float]) -> Dict[str, Any]:
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
    ivr = ((current_iv - low_52wk) / (high_52wk - low_52wk)) * 100 if (high_52wk - low_52wk) > 0 else 0

    # 計算 IV Percentile
    ivp = (np.sum(np.array(clean_iv_series) < current_iv) / len(clean_iv_series)) * 100

    return {
        "current_iv": current_iv,
        "iv_rank": round(ivr, 2),
        "iv_percentile": round(ivp, 2),
        "iv_52_week_high": high_52wk,
        "iv_52_week_low": low_52wk,
    }