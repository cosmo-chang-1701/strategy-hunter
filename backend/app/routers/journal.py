from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlmodel.ext.asyncio.session import AsyncSession
from .. import crud
from ..dependencies import get_db
from ..models import (
    User,
    TradeJournalEntryCreate,
    TradeJournalEntryRead,
)
from ..services import auth_service

router = APIRouter(
    prefix="/api/v1/journal", tags=["Trade Journal"]  # 在 API 文件中將它們分組
)


@router.post(
    "/",
    response_model=TradeJournalEntryRead,
    status_code=status.HTTP_201_CREATED,
    summary="建立新的交易日誌",
)
async def create_new_journal_entry(
    entry: TradeJournalEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_active_user),
):
    """
    建立一筆新的交易日誌項目。
    - **entry**: 包含交易日誌所有必要資訊的物件。
    """
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無法識別使用者身份",
        )
    return await crud.create_journal_entry(db=db, entry=entry, user_id=current_user.id)


@router.get("/", response_model=List[TradeJournalEntryRead], summary="讀取交易日誌列表")
async def read_journal_entries(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_active_user),
):
    """
    讀取交易日誌項目列表，支援分頁。
    - **skip**: 跳過的項目數量。
    - **limit**: 回傳的最大項目數量。
    """
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無法識別使用者身份",
        )
    return await crud.get_journal_entries(
        db, user_id=current_user.id, skip=skip, limit=limit
    )


@router.get(
    "/{entry_id}",
    response_model=TradeJournalEntryRead,
    summary="根據 ID 讀取單筆交易日誌",
    responses={404: {"description": "找不到指定的交易日誌"}},
)
async def read_journal_entry_by_id(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_active_user),
):
    """
    根據提供的 ID 獲取單筆交易日誌的詳細資訊。
    """
    db_entry = await crud.get_journal_entry(db, entry_id=entry_id)
    if db_entry is None:
        raise HTTPException(status_code=404, detail="找不到指定的交易日誌")
    if db_entry.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="沒有權限讀取此日誌"
        )
    return db_entry
