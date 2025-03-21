from typing import Dict
from pydantic import BaseModel, ConfigDict, EmailStr


class BaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AccessTokenResponse(BaseResponse):
    token_type: str = "Bearer"
    access_token: str
    expires_at: int
    refresh_token: str
    refresh_token_expires_at: int


class UserResponse(BaseResponse):
    user_group: str
    user_id: str

class ResponseMessage(BaseModel):
    status: str
    data: Dict # data is now a dictionary
    message: str
