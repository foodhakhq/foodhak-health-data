from sqlalchemy import Column, String, Boolean, JSON, Enum, DateTime, func, ForeignKey
from sqlalchemy.sql import func as sql_func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from enum import Enum as PyEnum

from models.base import Base
from models.user import FoodhakUser

class DeviceType(str, PyEnum):
    APPLE_HEALTH = "APPLE_HEALTH"
    GARMIN = "GARMIN"
    FITBIT = "FITBIT"
    HEALTH_CONNECT = "HEALTH_CONNECT"

class DeviceConnection(Base):
    __tablename__ = "device_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    foodhak_user_id = Column(UUID(as_uuid=True), ForeignKey('foodhak_users.id'), nullable=False, index=True)
    device_type = Column(Enum(DeviceType), nullable=False)
    is_connected = Column(Boolean, default=False)
    connection_details = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=sql_func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=sql_func.now())
    last_sync_at = Column(DateTime(timezone=True), nullable=True)

    # Relationship to FoodhakUser
    user = relationship("FoodhakUser", back_populates="device_connections")

    def __repr__(self):
        return f"<DeviceConnection(id={self.id}, device_type={self.device_type}, is_connected={self.is_connected})>" 