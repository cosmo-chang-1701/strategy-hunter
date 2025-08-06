from .database import SessionLocal
from .state import app_state
from .services.option_chain_service import OptionChainService


# 依賴注入：提供資料庫 session
async def get_db():
    async with SessionLocal() as db:
        yield db


# 依賴注入：提供 OptionChainService
def get_option_chain_service():
    is_live = app_state.get("polygon_options_accessible", False)
    return OptionChainService(is_live=is_live)
