from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    location_sharing_enabled: bool
    nearby_radius: float

    model_config = {"from_attributes": True}


class LocationSharingIn(BaseModel):
    enabled: bool


class RadiusIn(BaseModel):
    nearby_radius: float = Field(ge=0.1, le=50)


class NearbyFriendOut(BaseModel):
    user_id: uuid.UUID
    name: str
    latitude: float
    longitude: float
    distance_miles: float
    updated_at: datetime
    active: bool


class NearbyPageOut(BaseModel):
    origin_user_id: uuid.UUID
    radius_miles: float
    page: int
    page_size: int
    total: int
    friends: list[NearbyFriendOut]
    redis_available: bool = True


class HealthOut(BaseModel):
    status: str
    service: str
    instance_id: str
    postgres: str
    redis: str
