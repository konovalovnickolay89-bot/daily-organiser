"""Shared FastAPI dependencies."""

from fastapi import HTTPException, Request, status


def require_auth(request: Request) -> None:
    if request.session.get("authenticated") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
