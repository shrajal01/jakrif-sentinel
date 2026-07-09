from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional


class UserRegister(BaseModel):
    """
    Schema for user registration.
    """
    username: str = Field(..., min_length=3, max_length=100, description="Unique username")
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="Strong password")
    full_name: Optional[str] = Field(None, max_length=255, description="User's full name")


class Token(BaseModel):
    """
    Schema for access token response.
    """
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type, usually 'bearer'")


class TokenData(BaseModel):
    """
    Schema for extracted token data.
    """
    username: Optional[str] = None


class UserResponse(BaseModel):
    """
    Schema for user response.
    """
    id: int
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool
    is_superuser: bool

    model_config = ConfigDict(from_attributes=True)
