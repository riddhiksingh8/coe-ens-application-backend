from typing import Dict, Literal
from pydantic import BaseModel, EmailStr


class BaseRequest(BaseModel):
    # may define additional fields or config shared across requests
    pass


class RefreshTokenRequest(BaseRequest):
    refresh_token: str


class UserUpdatePasswordRequest(BaseRequest):
    password: str

class UserLoginRequest(BaseRequest):
    email: str
    password: str



class UserCreateRequest(BaseRequest):
    email: EmailStr
    password: str
    user_group: str
class RequestMessage(BaseModel):
    status: str
    data: Dict[str, str]  # data is now a dictionary
    message: str
  # Enum for status restriction

class BulkPayload(BaseModel):
    session_id: str
    status: Literal["accept", "reject"]  # Status must be "accept" or "reject"

class SinglePayloadItem(BaseModel):
    ens_id: str
    status: Literal["accept", "reject"]  # Status must be "accept" or "reject"