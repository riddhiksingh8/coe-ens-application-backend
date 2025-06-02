import secrets
import time
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.requests import *
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from app.api import api_messages, deps
from app.core.config import get_settings
from app.core.security.jwt import create_jwt_token
from app.core.security.password import (
    DUMMY_PASSWORD,
    create_unique_username,
    get_password_hash,
    verify_password,
)
from app.models import Base, RefreshToken, User
from app.schemas.requests import RefreshTokenRequest, UserCreateRequest
from app.schemas.responses import AccessTokenResponse, UserResponse
from app.schemas.logger import logger

router = APIRouter()

ACCESS_TOKEN_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {
        "description": "Invalid email or password",
        "content": {
            "application/json": {"example": {"detail": api_messages.PASSWORD_INVALID}}
        },
    },
}

REFRESH_TOKEN_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {
        "description": "Refresh token expired or is already used",
        "content": {
            "application/json": {
                "examples": {
                    "refresh token expired": {
                        "summary": api_messages.REFRESH_TOKEN_EXPIRED,
                        "value": {"detail": api_messages.REFRESH_TOKEN_EXPIRED},
                    },
                    "refresh token already used": {
                        "summary": api_messages.REFRESH_TOKEN_ALREADY_USED,
                        "value": {"detail": api_messages.REFRESH_TOKEN_ALREADY_USED},
                    },
                }
            }
        },
    },
    404: {
        "description": "Refresh token does not exist",
        "content": {
            "application/json": {
                "example": {"detail": api_messages.REFRESH_TOKEN_NOT_FOUND}
            }
        },
    },
}


@router.post(
    "/login",
    response_model=AccessTokenResponse,
    responses=ACCESS_TOKEN_RESPONSES,
    description="OAuth2 compatible token, get an access token for future requests using username and password",
)
async def login_access_token(
    form_data : UserLoginRequest,
     session: AsyncSession = Depends(deps.get_session)
) -> AccessTokenResponse:
    # user = await session.scalar(select(User).where(User.email == form_data.email))
    table_class = Base.metadata.tables.get("users_table")
    if table_class is None:
        raise ValueError("Table 'users_table' does not exist in the database schema.")

    query = select(table_class).where(table_class.c.email == str(form_data.email)).distinct()
    result = await session.execute(query)
    existing_user = result.fetchone()  # Use fetchone() instead of first()

    if existing_user:
        logger.debug(f"result: {dict(existing_user._mapping)}")  # Convert existing_user to dictionary and print
        existing_user = dict(existing_user._mapping)
    else:
        logger.warning("existing_user result: None")  # Handle no records found
        existing_user = None
    
    if existing_user is None:
        # this is naive method to not return early
        verify_password(form_data.password, DUMMY_PASSWORD)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_messages.USER_NOT_EXISTS,
        )
    
    if not verify_password(form_data.password, existing_user['password']):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_messages.PASSWORD_INVALID,
        )

    jwt_token = create_jwt_token(user_id=existing_user['user_id'], user_group=existing_user['user_group'])
    logger.debug(f"existing_user['user_id'] {existing_user['user_id']}")
    refresh_token_table = Base.metadata.tables.get("refresh_token")
    if refresh_token_table is None:
        raise ValueError("Table 'users_table' does not exist in the database schema.")
    refresh_token = {
        "refresh_token": secrets.token_urlsafe(32),
        "used": False,
        "exp": int(time.time() + get_settings().security.refresh_token_expire_secs),  # Example expiration time
        "user_id": str(existing_user['user_id']),
        "user_group": str(existing_user['user_group'])
    }

    query = insert(refresh_token_table).values(refresh_token)  # FIXED: No need for list
    await session.execute(query)

    try:
        await session.commit()
        return AccessTokenResponse(
            access_token=jwt_token.access_token,
            expires_at=jwt_token.payload.exp,
            refresh_token=refresh_token['refresh_token'],
            refresh_token_expires_at=refresh_token['exp'],
        )
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_messages.EMAIL_ADDRESS_ALREADY_USED,
        )
    
    refresh_token = RefreshToken(
        user_id=existing_user['user_id'],
        refresh_token=secrets.token_urlsafe(32),
        exp=int(time.time() + get_settings().security.refresh_token_expire_secs),
    )
    session.add(refresh_token)
    await session.commit()

    return AccessTokenResponse(
        access_token=jwt_token.access_token,
        expires_at=jwt_token.payload.exp,
        refresh_token=refresh_token.refresh_token,
        refresh_token_expires_at=refresh_token.exp,
    )


@router.post(
    "/refresh-token",
    response_model=AccessTokenResponse,
    responses=REFRESH_TOKEN_RESPONSES,
    description="OAuth2 compatible token, get an access token for future requests using refresh token",
)
async def refresh_token(
    data: RefreshTokenRequest,
    session: AsyncSession = Depends(deps.get_session),
) -> AccessTokenResponse:
    refresh_token_table = Base.metadata.tables.get("refresh_token")
    if refresh_token_table is None:
        raise ValueError("Table 'refresh_token' does not exist in the database schema.")

    query = select(refresh_token_table).where(refresh_token_table.c.refresh_token == data.refresh_token).with_for_update(skip_locked=True)
    result = await session.execute(query)
    token = result.mappings().first()

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_messages.REFRESH_TOKEN_NOT_FOUND,
        )
    elif time.time() > token["exp"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_messages.REFRESH_TOKEN_EXPIRED,
        )
    elif token["used"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_messages.REFRESH_TOKEN_ALREADY_USED,
        )

    # ✅ Use an UPDATE query instead of modifying a dictionary
    update_stmt = (
        refresh_token_table.update()
        .where(refresh_token_table.c.refresh_token == data.refresh_token)
        .values(used=True)
    )
    await session.execute(update_stmt)

    # ✅ Create new refresh token
    new_refresh_token = {
        "refresh_token": secrets.token_urlsafe(32),
        "exp": int(time.time() + get_settings().security.refresh_token_expire_secs),
        "user_id": str(token["user_id"]),
        "used": False,  # New refresh tokens are initially unused
    }

    insert_stmt = insert(refresh_token_table).values(new_refresh_token)
    await session.execute(insert_stmt)

    # ✅ Commit changes
    await session.commit()

    jwt_token = create_jwt_token(user_id=token["user_id"], user_group=token['user_group'])

    return AccessTokenResponse(
        access_token=jwt_token.access_token,
        expires_at=jwt_token.payload.exp,
        refresh_token=new_refresh_token["refresh_token"],
        refresh_token_expires_at=new_refresh_token["exp"],
    ) 
    refresh_token = RefreshToken(
        user_id=token['user_id'],
        refresh_token=secrets.token_urlsafe(32),
        exp=int(time.time() + get_settings().security.refresh_token_expire_secs),
    )
    session.add(refresh_token)
    await session.commit()

    return AccessTokenResponse(
        access_token=jwt_token.access_token,
        expires_at=jwt_token.payload.exp,
        refresh_token=refresh_token.refresh_token,
        refresh_token_expires_at=refresh_token.exp,
    )


@router.post(
    "/register",
    description="Create new user",
    status_code=status.HTTP_201_CREATED,
)
async def register_new_user(
    new_user: UserCreateRequest,
    session: AsyncSession = Depends(deps.get_session),
):
    logger.info(f"Registering new user: {new_user.email}")
    table_class = Base.metadata.tables.get("users_table")
    if table_class is None:
        raise ValueError("Table 'users_table' does not exist in the database schema.")

    query = select(table_class).where(table_class.c.email == str(new_user.email)).distinct()
    result = await session.execute(query)
    
    existing = result.scalar_one_or_none()  # FIXED: Correct way to check if user exists

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_messages.EMAIL_ADDRESS_ALREADY_USED,
        )

    # Prepare user data for insertion
    user_data = {
        "username": create_unique_username(new_user.email),
        "user_id": str(uuid.uuid4()),
        "email": new_user.email,
        "password": get_password_hash(new_user.password),
        "verified": False,
        "user_group": new_user.user_group,
        "otp": "0000"
    }

    query = insert(table_class).values(user_data)  # FIXED: No need for list
    await session.execute(query)

    try:
        await session.commit()
        user_data
        # Remove password safely
        user_data.pop("password", None)  # Removes 'password' if it exists, otherwise does nothing
        return {"message": "User registered successfully", "user": user_data}
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_messages.EMAIL_ADDRESS_ALREADY_USED,
        )
