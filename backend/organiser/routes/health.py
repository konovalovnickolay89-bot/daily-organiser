from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from organiser import __version__
from organiser.db import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(session: Session = Depends(get_db)) -> dict:
    session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok", "version": __version__}
