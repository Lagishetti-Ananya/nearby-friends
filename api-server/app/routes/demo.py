from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.schemas.user import UserOut
from app.services import user_service

router = APIRouter(tags=["demo"])


@router.get("/demo/users", response_model=list[UserOut])
async def demo_users(session: AsyncSession = Depends(get_session)):
    """Seeded demo identities for the hackathon UI. Demo simplification — not auth."""
    return await user_service.list_users(session, limit=20)
