import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import Token, UserCreate, UserResponse

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Registers a new user asynchronously. Checks if the username or email is already registered.
    """
    username_result = await db.execute(
        select(User).filter(User.username == user_in.username)
    )
    db_user = username_result.scalars().first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    email_result = await db.execute(select(User).filter(User.email == user_in.email))
    db_email = email_result.scalars().first()
    if db_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    hashed_pass = await get_password_hash(user_in.password)
    new_user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hashed_pass,
        role=user_in.role,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@router.post("/login", response_model=Token)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    query_result = await db.execute(
        select(User).filter(
            (User.username == form_data.username) | (User.email == form_data.username)
        )
    )
    user = query_result.scalars().first()

    if not user or not await verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=30 * 24 * 60 * 60,
        samesite="lax",
        secure=False,
        path="/",
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh", response_model=Token)
async def refresh(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
):
    """
    Validates the secure HttpOnly Refresh Token, rotates it,
    and issues a brand new Access Token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise credentials_exception

    try:
        payload = jwt.decode(
            refresh_token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "refresh":
            raise credentials_exception

        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception

    user_result = await db.execute(select(User).filter(User.username == username))
    user = user_result.scalars().first()
    if user is None:
        raise credentials_exception

    new_access_token = create_access_token(data={"sub": user.username})
    new_refresh_token = create_refresh_token(data={"sub": user.username})

    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        max_age=30 * 24 * 60 * 60,
        samesite="lax",
        secure=False,
        path="/",
    )

    return {"access_token": new_access_token, "token_type": "bearer"}


@router.post("/logout")
async def logout(response: Response):
    """
    Logs out the user by deleting the HttpOnly refresh token cookie.
    """
    response.delete_cookie(key="refresh_token", httponly=True, samesite="lax", path="/")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Returns the currently authenticated user's profile details.
    """
    return current_user
