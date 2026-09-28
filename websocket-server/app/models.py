from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    location_sharing_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    nearby_radius: Mapped[float] = mapped_column(Float, default=5.0)


class Friendship(Base):
    __tablename__ = "friendships"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    friend_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)


class LocationHistory(Base):
    __tablename__ = "location_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    latitude: Mapped[float] = mapped_column()
    longitude: Mapped[float] = mapped_column()
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
