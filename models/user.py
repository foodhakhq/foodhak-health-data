from sqlalchemy import Column, String, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from models.base import Base

class FoodhakUser(Base):
    __tablename__ = "foodhak_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship to DeviceConnection
    device_connections = relationship("DeviceConnection", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<FoodhakUser(id={self.id}, email={self.email})>" 