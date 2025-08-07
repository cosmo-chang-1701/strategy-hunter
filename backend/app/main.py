import os
import httpx
import logging

from fastapi import FastAPI
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from .database import engine, Base

from .state import app_state
from .routers import journal, market_data, options, risk, strategies, volatility

# 在應用程式啟動時，載入 .env 檔案中的環境變數
load_dotenv()

# 設定日誌記錄器
logging.basicConfig(level=logging.INFO, format="%(levelname)-8s: %(message)s")
log = logging.getLogger(__name__)


# --- FastAPI 生命週期管理器 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Application startup...")

    # 檢查 Polygon.io 的選擇權快照存取權限
    log.info("Performing Polygon.io v3 options access check...")
    app_state["polygon_options_accessible"] = await check_polygon_options_access()
    if app_state["polygon_options_accessible"]:
        log.info("Polygon.io v3 options snapshot access: VERIFIED")
    else:
        log.warning(
            "Polygon.io v3 options snapshot access: FAILED. Option chain will use mock data."
        )

    # 建立資料庫表格
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # 如果需要，可取消註解以在每次重啟時刪除舊表
        await conn.run_sync(Base.metadata.create_all)
    log.info("Database tables created.")

    yield
    log.info("Application shutdown.")
    app_state.clear()


# ---建立 FastAPI 應用程式實例 ---
app = FastAPI(
    title="美股選擇權分析平台 API",
    description="提供美股市場數據、選擇權鏈、策略分析等功能。",
    version="1.0.0",
    lifespan=lifespan,
)

# --- 掛載路由 ---
# 將不同功能的 API 端點註冊到我們的應用程式中
app.include_router(journal.router)
app.include_router(market_data.router)
app.include_router(options.router)
app.include_router(risk.router)
app.include_router(strategies.router)
app.include_router(volatility.router)


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
                for item in data.get("results", []):
                    if item.get("ticker") == "O:SPY250815C00550000" and not item.get(
                        "error"
                    ):
                        return True  # 找到選擇權且沒有錯誤
            return False
    except Exception as e:
        log.error(f"ERROR during Polygon access check: {e}")
        return False


@app.get("/")
async def read_root():
    return {"message": "歡迎使用美股選擇權分析平台 API"}
