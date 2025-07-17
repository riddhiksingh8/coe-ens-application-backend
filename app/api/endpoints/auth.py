from datetime import datetime, timedelta
import secrets
import time
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Header, status, Response
from fastapi.responses import JSONResponse
from app.schemas.requests import *
from sqlalchemy import and_, or_, select, update
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
from app.schemas.responses import APIKeyResponse, AccessTokenResponse, UserResponse
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
    form_data: UserLoginRequest,
    session: AsyncSession = Depends(deps.get_session)
) -> JSONResponse:
    table_class = Base.metadata.tables.get("users_table")
    if table_class is None:
        raise ValueError("Table 'users_table' does not exist in the database schema.")

    query = select(table_class).where(table_class.c.email == str(form_data.email)).distinct()
    result = await session.execute(query)
    existing_user = result.fetchone()

    if existing_user:
        existing_user = dict(existing_user._mapping)
    else:
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
    refresh_token_table = Base.metadata.tables.get("refresh_token")
    if refresh_token_table is None:
        raise ValueError("Table 'refresh_token' does not exist in the database schema.")

    refresh_token = {
        "refresh_token": secrets.token_urlsafe(32),
        "used": False,
        "exp": int(time.time() + get_settings().security.refresh_token_expire_secs),
        "user_id": str(existing_user['user_id']),
        "user_group": str(existing_user['user_group'])
    }

    query = insert(refresh_token_table).values(refresh_token)
    await session.execute(query)

    try:
        await session.commit()

        # Create response and set access_token cookie
        response = JSONResponse(
            content={
                "access_token": jwt_token.access_token,
                "expires_at": jwt_token.payload.exp,
                "refresh_token": refresh_token['refresh_token'],
                "refresh_token_expires_at": refresh_token['exp'],
            }
        )
        response.set_cookie(
            key="access_token",
            value=jwt_token.access_token,
            httponly=True,
            secure=False,  # set to True in production with HTTPS
            samesite="strict",
            max_age=60 * 60  # 1 hour
        )
        return response

    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_messages.EMAIL_ADDRESS_ALREADY_USED,
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


def generate_api_key():
    return secrets.token_urlsafe(32)


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
    key= str(generate_api_key())
    uid = str(uuid.uuid4())
    expires_in_days = 30
    key_expire = datetime.utcnow() + timedelta(days=expires_in_days)
    # Prepare user data for insertion
    user_data = {
        "username": create_unique_username(new_user.email),
        "user_id": uid,
        "email": new_user.email,
        "password": get_password_hash(new_user.password),
        "verified": False,
        "user_group": new_user.user_group,
        "api_key": key, 
        "key_expires_at": key_expire,
        "otp": "0000"
    }

    query = insert(table_class).values(user_data)  # FIXED: No need for list
    await session.execute(query)

    try:
        await session.commit()
        user_data

        api_key_table = Base.metadata.tables.get("api_keys")
        if api_key_table is None:
            raise HTTPException(status_code=500, detail="API keys table not found")
        
        await session.execute(insert(api_key_table).values(
            api_key=key,
            user_id=uid,
            expires_at=key_expire,
            is_active=True
        ))
        await session.commit()
        # Remove password safely
        user_data.pop("password", None)  # Removes 'password' if it exists, otherwise does nothing
        return {"message": "User registered successfully", "user": user_data}
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_messages.EMAIL_ADDRESS_ALREADY_USED,
        )

# @router.post(
#     "/api-key-login",
#     response_model=AccessTokenResponse,
#     description="Authenticate using an API key"
# )
# async def api_key_login(
#     api_key: str = Header(..., alias="X-API-KEY"),
#     session: AsyncSession = Depends(deps.get_session),
# ) -> AccessTokenResponse:
#     api_keys_table = Base.metadata.tables.get("api_keys")
#     if api_keys_table is None:
#         raise HTTPException(status_code=500, detail="API keys table not found")

#     query = select(api_keys_table).where(
#         api_keys_table.c.api_key == api_key,
#         api_keys_table.c.is_active == True,
#         or_(api_keys_table.c.expires_at.is_(None), api_keys_table.c.expires_at > datetime.utcnow())
#     )
#     result = await session.execute(query)
#     key = result.mappings().first()

#     if not key:
#         raise HTTPException(status_code=403, detail="Invalid or expired API key")

#     # JWT + refresh
#     jwt_token = create_jwt_token(user_id=None, user_group=key["user_group"])

#     refresh_token_table = Base.metadata.tables.get("refresh_token")
#     new_refresh_token = {
#         "refresh_token": secrets.token_urlsafe(32),
#         "exp": int(time.time() + get_settings().security.refresh_token_expire_secs),
#         "user_id": None,
#         "user_group": key["user_group"],
#         "used": False,
#     }

#     await session.execute(insert(refresh_token_table).values(new_refresh_token))
#     await session.commit()

#     return AccessTokenResponse(
#         access_token=jwt_token.access_token,
#         expires_at=jwt_token.payload.exp,
#         refresh_token=new_refresh_token["refresh_token"],
#         refresh_token_expires_at=new_refresh_token["exp"],
#     )

@router.post(
    "/update-api-key",
    response_model=APIKeyResponse,
    status_code=status.HTTP_201_CREATED,
    description="Update a new API key for a autharized user",
)
async def update_api_key(
    request: APIKeyCreateRequest,
    session: AsyncSession = Depends(deps.get_session),
    current_user_id: dict = Depends(deps.get_current_user),
):
    user_id = request.user_id
    users_table = Base.metadata.tables.get("users_table")
    api_keys_table = Base.metadata.tables.get("api_keys")

    if users_table is None or api_keys_table is None:
        raise HTTPException(status_code=500, detail="Tables missing")

    key = generate_api_key()
    expiry = datetime.utcnow() + timedelta(days=request.expires_in_days)

    try:
        # 1. Deactivate all old keys
        await session.execute(
            update(api_keys_table)
            .where(
                and_(
                    api_keys_table.c.user_id == user_id,
                    api_keys_table.c.is_active == True
                )
            )
            .values(is_active=False)
        )

        # 2. Insert new key
        await session.execute(
            insert(api_keys_table).values(
                api_key=key,
                user_id=user_id,
                expires_at=expiry,
                is_active=True
            )
        )

        # 3. Update user record
        await session.execute(
            update(users_table)
            .where(users_table.c.user_id == user_id)
            .values(
                key_expires_at=expiry,
                api_key=key
            )
        )

        # 4. Final commit
        await session.commit()

    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to update API key for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update API key")

    return APIKeyResponse(
        api_key=key,
        expires_at=expiry,
        is_active=True
    )