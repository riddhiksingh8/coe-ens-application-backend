from datetime import datetime
from typing import Dict, Optional
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

class APIKeyResponse(BaseModel):
    api_key: str
    expires_at: Optional[datetime]
    is_active: bool = True

class ENSProcessingResponse(BaseModel):
    session_id: str
    rows_inserted: int
    session_screening_status: str
    ens_ids_processed: int

class SessionCreationResponse(BaseModel):
    session_id: str
    rows_inserted: int
    session_screening_status: str
    ens_ids_processed: int

