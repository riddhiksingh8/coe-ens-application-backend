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
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Accept Bearer Token directly in headers
api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

async def get_session() -> AsyncGenerator[AsyncSession]:
    async with database_session.get_async_session() as session:
        yield session
def is_tprp_route(path: str) -> bool:
    return path.startswith("/tprp")  # Modify this based on how you match TPRP routes
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
    print("token_payload", token_payload)

    table_class = Base.metadata.tables.get("users_table")
    if table_class is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Table 'users_table' does not exist in the database schema."
        )

    # Execute async query to fetch user with matching user_id and user_grp
    query = select(table_class).where(
        table_class.c.user_id == token_payload.sub,  # Match user_id
        table_class.c.user_group == token_payload.ugr  # Match user_grp
    )
    result = await session.execute(query)
    user = result.fetchone()
    print("user", user)
    # If no user is found, raise an error
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=api_messages.JWT_ERROR_USER_REMOVED,
        )

    # Extract email (since `user` is a tuple, access it by index)
    email = user[2]  

    # If the user is the admin (admin.tprp.secure@tprp.com)
    if email == "admin.tprp.secure@tprp.com":
        # If trying to access any endpoint other than /tprp, deny access
        if not is_tprp_route(path):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin user is restricted to TPRP endpoints only"
            )

    # 🚨 Log and restrict if a non-admin user tries to access TPRP APIs
    if "tprp" in path and email != "admin.tprp.secure@tprp.com":
        logger.warning(f"Unauthorized TPRP access attempt by {email} on {path}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin is allowed to access TPRP APIs"
        )

    return user