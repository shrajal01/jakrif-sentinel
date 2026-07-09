from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi.security import OAuth2PasswordRequestForm

from app.database.session import get_db
from app.schemas.auth import UserRegister, Token, UserResponse
from app.services import auth_service
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    user_in: UserRegister,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user in the system.
    """
    return await auth_service.create_user(db, user_in)


@router.post(
    "/login",
    response_model=Token,
    summary="Login user",
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate user and return a JWT access token.
    """
    return await auth_service.login_user(db, form_data.username, form_data.password)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
)
async def get_me(
    current_user: User = Depends(auth_service.get_current_user),
):
    """
    Get the currently authenticated user based on the provided JWT token.
    """
    return current_user
