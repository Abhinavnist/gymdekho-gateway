from typing import Annotated

import psycopg
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.core.exceptions import UnauthorizedException, ForbiddenException
from app.core.security import decode_token
from app.database.connection import get_db
from app.database.queries import user_queries

bearer_scheme = HTTPBearer(auto_error=False)

DBConn = Annotated[psycopg.AsyncConnection, Depends(get_db)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DBConn,
) -> dict:
    if not credentials:
        raise UnauthorizedException()
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise UnauthorizedException("Invalid token type.")
        user_id: int = payload.get("sub")
        if not user_id:
            raise UnauthorizedException()
    except JWTError:
        raise UnauthorizedException("Token is invalid or expired.")

    user = await user_queries.get_user_by_id(db, int(user_id))
    if not user:
        raise UnauthorizedException("User not found.")
    if not user["is_active"]:
        raise UnauthorizedException("Account is deactivated.")
    return user


CurrentUser = Annotated[dict, Depends(get_current_user)]


def require_roles(*roles: str):
    """Factory that returns a dependency enforcing one of the given roles."""
    async def _check(current_user: CurrentUser):
        if current_user["role"] not in roles:
            raise ForbiddenException()
        return current_user
    return _check


# Convenience role dependencies
RequireAdmin       = Depends(require_roles("SUPER_ADMIN", "ADMIN"))
RequireGymOwner    = Depends(require_roles("SUPER_ADMIN", "ADMIN", "GYM_OWNER", "GYM_MANAGER"))
RequireTrainer     = Depends(require_roles("SUPER_ADMIN", "ADMIN", "TRAINER"))
RequireSuperAdmin  = Depends(require_roles("SUPER_ADMIN"))
