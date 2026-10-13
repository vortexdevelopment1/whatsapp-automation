import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr


class AdminUserBase(BaseModel):
    email: EmailStr
    full_name: str


class AdminUserCreate(AdminUserBase):
    password: str


class AdminUserResponse(AdminUserBase):
    id: uuid.UUID
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
