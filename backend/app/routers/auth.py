from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel.ext.asyncio.session import AsyncSession
from datetime import timedelta

from .. import models, crud
from ..services import auth_service

from ..config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=models.User,
    status_code=status.HTTP_201_CREATED,
    summary="註冊新使用者",
)
async def register_user(
    user: models.UserCreate, db: AsyncSession = Depends(auth_service.get_db)
):
    """
    註冊新使用者
    """
    db_user = await crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return await crud.create_user(db=db, user=user)


@router.post(
    "/login", response_model=models.Token, summary="使用者登入並獲取 JWT Token"
)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(auth_service.get_db),
):
    """
    使用者登入並獲取 JWT Token
    """
    user = await crud.get_user_by_username(db, username=form_data.username)
    if not user or not auth_service.verify_password(
        form_data.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}
