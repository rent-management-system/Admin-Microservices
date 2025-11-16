from sqlalchemy import Column, UUID, String, JSON, DateTime
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
import uuid

class Base(AsyncAttrs, DeclarativeBase):
    pass

class AdminLog(Base):
    __tablename__ = "AdminLogs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String(255), nullable=False)
    entity_id = Column(UUID(as_uuid=True))
    details = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
