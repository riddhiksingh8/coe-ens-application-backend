from fastapi import APIRouter

from app.api import api_messages
from app.api.endpoints import auth, users, supplier, report, tprp, streaming, graph

auth_router = APIRouter()
auth_router.include_router(auth.router, prefix="/auth", tags=["auth"])

api_router = APIRouter(
    responses={
        401: {
            "description": "No `Authorization` access token header, token is invalid or user removed",
            "content": {
                "application/json": {
                    "examples": {
                        "not authenticated": {
                            "summary": "No authorization token header",
                            "value": {"detail": "Not authenticated"},
                        },
                        "invalid token": {
                            "summary": "Token validation failed, decode failed, it may be expired or malformed",
                            "value": {"detail": "Token invalid: {detailed error msg}"},
                        },
                        "removed user": {
                            "summary": api_messages.JWT_ERROR_USER_REMOVED,
                            "value": {"detail": api_messages.JWT_ERROR_USER_REMOVED},
                        },
                    }
                }
            },
        },
    }
)
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(supplier.router, prefix="/supplier", tags=["supplier"])
api_router.include_router(report.router, prefix="/report", tags=["Report"])
api_router.include_router(tprp.router, prefix="/tprp", tags=["TPRP"])
api_router.include_router(streaming.router, prefix="/streaming", tags=["streaming"])

api_router.include_router(graph.router, prefix="/graph", tags=["graph"])
