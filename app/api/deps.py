from collections.abc import AsyncGenerator
from typing import Annotated
from fastapi import Depends, HTTPException, Request, status, Security
from sqlalchemy import select
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
    request: Request,  # Get the request path
    authorization: str = Security(api_key_header),
    session: AsyncSession = Depends(get_session)
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token",
        )

    token = authorization.split("Bearer ")[1]  # Extract the actual token

    # Extract the current request path
    path = request.url.path

    # Verify the JWT token
    token_payload = verify_jwt_token(token)
    logger.debug(f"token_payload, {token_payload}")

    table_class = Base.metadata.tables.get("users_table")
    if table_class is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Table 'users_table' does not exist in the database schema."
        )

    # Execute async query to fetch user with matching user_id and user_group
    query = select(table_class.c.user_group, table_class.c.user_id).where(
        table_class.c.user_id == token_payload.sub,  # Match user_id
        table_class.c.user_group == token_payload.ugr  # Match user_group
    )
    result = await session.execute(query)
    user = result.fetchone()
    # If no user is found, raise an error
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=api_messages.JWT_ERROR_USER_REMOVED,
        )
    logger.debug(f"user {user}")
    # Extract user group (assuming it's the 3rd column in the tuple)
    user_group = user[0]  

    # Reject if user_group is invalid
    allowed_groups = {"tprp_admin", "general", "super_admin"}
    logger.debug(f"user_group {user_group}")
    if user_group not in allowed_groups:
        logger.error(f"Unauthorized access attempt with invalid user_group: {user_group}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user group"
        )
    if user_group != "super_admin":
        #`tprp_admin` can ONLY access `/tprp` routes
        if user_group == "tprp_admin" and not is_tprp_route(path):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Users are restricted to TPRP endpoints only"
            )

        #`general` users CANNOT access `/tprp` routes
        if user_group == "general" and is_tprp_route(path):
            logger.warning(f"Unauthorized TPRP access attempt by general user on {path}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="General users are not allowed to access TPRP APIs"
            )

    return user