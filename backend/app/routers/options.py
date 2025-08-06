from fastapi import APIRouter, Depends
from typing import List

from .. import schemas
from ..dependencies import get_option_chain_service
from ..services.option_chain_service import OptionChainService

router = APIRouter(
    prefix="/api/v1/stocks/{ticker}/options",
    tags=["Options"],
)


@router.get("", response_model=schemas.OptionChain, summary="獲取選擇權鏈資料")
async def get_option_chain(
    ticker: str,
    expiration_date: str,
    service: OptionChainService = Depends(get_option_chain_service),
):
    return await service.get_option_chain(ticker, expiration_date)


@router.get("/expirations", response_model=List[str], summary="獲取選擇權到期日列表")
async def get_option_expirations(
    ticker: str, service: OptionChainService = Depends(get_option_chain_service)
):
    """
    獲取指定股票所有可用的選擇權到期日列表。
    """
    return await service.fetch_option_expirations(ticker)
