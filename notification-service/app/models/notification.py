from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any, Union

from app.db.postgresql import Base


# SQLAlchemy Models
class NotificationPreference(Base):
    """Database model for user notification preferences."""
    __tablename__ = "notification_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    channel = Column(String, nullable=False)  # "email", "sms", etc.
    enabled = Column(Boolean, nullable=False, default=True)
    
    # For email notifications
    email = Column(String, nullable=True)
    
    # For SMS notifications
    phone = Column(String, nullable=True)
    
    # For webhook notifications
    webhook_url = Column(String, nullable=True)
    
    # Notification type specific settings
    settings = Column(JSON, nullable=True)  # Store channel-specific settings as JSON
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class NotificationTemplate(Base):
    """Database model for notification templates."""
    __tablename__ = "notification_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    type = Column(String, nullable=False)  # "low_stock", "order_status", etc.
    channel = Column(String, nullable=False)  # "email", "sms", etc.
    subject = Column(String, nullable=True)  # For email notifications
    body = Column(Text, nullable=False)  # Template body (supports Jinja2)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Notification(Base):
    """Database model for notifications."""
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=True)  # Nullable for system notifications
    type = Column(String, nullable=False)  # "low_stock", "order_status", etc.
    channel = Column(String, nullable=False)  # "email", "sms", "database", etc.
    
    # Content
    subject = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    
    # Delivery status
    status = Column(String, nullable=False, default="pending")  # "pending", "sent", "failed", "read"
    error_message = Column(String, nullable=True)
    
    # Data used to generate the notification
    data = Column(JSON, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    sent_at = Column(DateTime(timezone=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)


# Pydantic Models for API
class NotificationPreferenceBase(BaseModel):
    """Base model for notification preferences."""
    user_id: str
    channel: str
    enabled: bool = True
    email: Optional[str] = None
    phone: Optional[str] = None
    webhook_url: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class NotificationPreferenceCreate(NotificationPreferenceBase):
    """Model for creating notification preferences."""
    pass


class NotificationPreferenceUpdate(BaseModel):
    """Model for updating notification preferences."""
    enabled: Optional[bool] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    webhook_url: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class NotificationPreferenceResponse(NotificationPreferenceBase):
    """Model for notification preference response."""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


class NotificationBase(BaseModel):
    """Base model for notifications."""
    user_id: Optional[str] = None
    type: str
    channel: str
    subject: Optional[str] = None
    content: str
    data: Optional[Dict[str, Any]] = None


class NotificationCreate(NotificationBase):
    """Model for creating a notification."""
    pass


class NotificationResponse(NotificationBase):
    """Model for notification response."""
    id: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True


class NotificationSummary(BaseModel):
    """Summary of notification status for a user."""
    total: int
    unread: int
    
    class Config:
        orm_mode = True