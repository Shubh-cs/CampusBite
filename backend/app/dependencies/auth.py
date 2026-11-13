from collections.abc import Callable
from typing import Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import JWTConfigurationError, decode_access_token
from app.database import get_db
from app.models.user import User

UserRole = Literal["CUSTOMER", "OWNER", "DELIVERY_PARTNER"]
ALLOWED_ROLES = frozenset({"CUSTOMER", "OWNER", "DELIVERY_PARTNER"})
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
        if user_id <= 0:
            raise ValueError("Invalid subject.")
    except (InvalidTokenError, JWTConfigurationError, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, JWTConfigurationError):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication is not configured. Set a secure JWT_SECRET_KEY.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.scalar(
        select(User)
        .where(User.id == user_id)
        .execution_options(populate_existing=True)
    )
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    if not roles:
        raise ValueError("require_roles needs at least one permitted role.")
    if any(role not in ALLOWED_ROLES for role in roles):
        raise ValueError("require_roles received an unsupported role.")

    permitted_roles = frozenset(roles)

    def role_dependency(current_user: User = Depends(get_current_user)) -> User:
        # current_user was loaded from the database for this request; token claims are not used.
        if current_user.role not in permitted_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )
        return current_user

    return role_dependency
