from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Annotated
from fastapi import Depends, HTTPException, Request, WebSocket, WebSocketException, status, Security
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import APIKeyHeader

from app.api import api_messages
from app.core import database_session
from app.core.security.jwt import verify_jwt_token
from app.models import User, Base
from app.schemas.logger import logger

# Accept Bearer Token directly in headers
api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

async def get_session() -> AsyncGenerator[AsyncSession]:
    async with database_session.get_async_session() as session:
        yield session
def is_tprp_route(path: str) -> bool:
    return "tprp" in path  # Modify this based on how you match TPRP routes

async def get_current_user(
    request: Request,
    authorization: str = Security(api_key_header),
    session: AsyncSession = Depends(get_session),
):
    if authorization and authorization.startswith("Bearer "):

        token = authorization.split("Bearer ")[1]
        token_payload = verify_jwt_token(token)
        logger.debug(f"token_payload: {token_payload}")

        # Extract user_group
        user_group = getattr(token_payload, "ugr", None)
        user_id = getattr(token_payload, "sub", None)

        if not user_group:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing user group"
            )

        # If user_id is present, validate from DB (username/password flow)
        if user_id:
            table_class = Base.metadata.tables.get("users_table")
            if table_class is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Table 'users_table' does not exist in the database schema."
                )

            query = select(table_class.c.user_group, table_class.c.user_id).where(
                table_class.c.user_id == user_id,
                table_class.c.user_group == user_group
            )
            result = await session.execute(query)
            user = result.fetchone()
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=api_messages.JWT_ERROR_USER_REMOVED,
                )
            logger.debug(f"user from DB: {user}")
            user_group = user[0]  # just to be sure

    elif authorization:
        auth_api_key = authorization  # Use this directly as API key
        
        users_table = Base.metadata.tables.get("users_table")
        api_keys_table = Base.metadata.tables.get("api_keys")
        if (users_table is None) or (api_keys_table is None):
            raise HTTPException(status_code=500, detail="Tables missing")

        query = (
            select(
                users_table.c.user_group,
                users_table.c.user_id,
                users_table.c.key_expires_at,
                api_keys_table.c.api_key,
                api_keys_table.c.expires_at,
            )
            .select_from(users_table.join(api_keys_table, users_table.c.user_id == api_keys_table.c.user_id))
            .where(
                api_keys_table.c.api_key == auth_api_key,
                api_keys_table.c.is_active == True,
                or_(
                    api_keys_table.c.expires_at.is_(None),
                    api_keys_table.c.expires_at > datetime.utcnow()
                )
            )
        )

        result = await session.execute(query)
        user = result.mappings().first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid API key")
        user_id = user["user_id"]
        user_group = user["user_group"]
        if user["key_expires_at"] and user["key_expires_at"] < datetime.utcnow():
            raise HTTPException(status_code=401, detail="API key expired")
    
    else:
        # Try reading JWT token from HTTP-only cookie
        token = request.cookies.get("access_token")
        if not token:
            raise HTTPException(status_code=401, detail="Missing Authorization token or cookie")
        
        token_payload = verify_jwt_token(token)
        logger.debug(f"token_payload: {token_payload}")

        user_group = getattr(token_payload, "ugr", None)
        user_id = getattr(token_payload, "sub", None)

        if not user_group or not user_id:
            raise HTTPException(status_code=401, detail="Invalid cookie token payload")

        # Validate from DB
        table_class = Base.metadata.tables.get("users_table")
        if table_class is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Table 'users_table' does not exist in the database schema."
            )

        query = select(table_class.c.user_group, table_class.c.user_id).where(
            table_class.c.user_id == user_id,
            table_class.c.user_group == user_group
        )
        result = await session.execute(query)
        user = result.fetchone()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=api_messages.JWT_ERROR_USER_REMOVED,
            )
    # Route-based group restriction
    path = request.url.path
    allowed_groups = {"tprp_admin", "general", "super_admin"}

    if user_group not in allowed_groups:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user group"
        )

    if user_group != "super_admin":
        if user_group == "tprp_admin" and not is_tprp_route(path):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="TPRP admin can only access TPRP endpoints"
            )
        if user_group == "general" and is_tprp_route(path):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="General users are not allowed to access TPRP APIs"
            )

    return {"user_group": user_group, "user_id": user_id}

async def get_current_user_from_ws(websocket: WebSocket, session: AsyncSession) -> dict:
    # Extract API key from Authorization header
    api_key = websocket.headers.get("Authorization")
    print("api_key", api_key)
    if not api_key:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION,
            reason="Authorization header is missing")

    users_table = Base.metadata.tables.get("users_table")
    api_keys_table = Base.metadata.tables.get("api_keys")

    if (users_table is None) or (api_keys_table is None):
            raise HTTPException(status_code=500, detail="Database tables missing")

    query = (
        select(
            users_table.c.user_group,
            users_table.c.user_id,
            users_table.c.key_expires_at,
            api_keys_table.c.api_key,
            api_keys_table.c.expires_at,
        )
        .select_from(users_table.join(api_keys_table, users_table.c.user_id == api_keys_table.c.user_id))
        .where(
            api_keys_table.c.api_key == api_key,
            api_keys_table.c.is_active == True,
            or_(
                api_keys_table.c.expires_at.is_(None),
                api_keys_table.c.expires_at > datetime.utcnow()
            )
        )
    )

    result = await session.execute(query)
    user = result.mappings().first()
    if not user:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired API key")

    if user["key_expires_at"] and user["key_expires_at"] < datetime.utcnow():
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="API key expired")

    user_group = user["user_group"]
    if user_group not in {"tprp_admin", "general", "super_admin"}:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="User group not allowed")

    return {"user_group": user_group, "user_id": user["user_id"]}