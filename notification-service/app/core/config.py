import os
from typing import Optional, Dict, Any, List

from pydantic import BaseSettings, AnyHttpUrl, validator, PostgresDsn, RedisDsn, EmailStr


class Settings(BaseSettings):
    # API settings
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    PROJECT_NAME: str = "Notification Service"
    PORT: int = 8004
    
    # Database settings
    DATABASE_URL: PostgresDsn
    
    # Service URLs
    USER_SERVICE_URL: Optional[AnyHttpUrl] = None
    
    # JWT Auth settings (for testing/development)
    SECRET_KEY: str = "development-secret-key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Redis settings for notifications
    REDIS_URL: RedisDsn = "redis://redis:6379/0"
    NOTIFICATION_CHANNEL: str = "inventory:low-stock"
    
    # Email settings
    SMTP_HOST: str = "sandbox.smtp.mailtrap.io"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: Optional[EmailStr] = None
    EMAIL_FROM_NAME: str = "E-commerce Notifications"
    
    # Admin email for receiving low stock notifications
    ADMIN_EMAIL: Optional[EmailStr] = "admin@example.com"
    
    # Notification processing settings
    NOTIFICATION_BATCH_SIZE: int = 10
    NOTIFICATION_PROCESSING_INTERVAL: int = 30  # seconds
    
    # Notification channels
    NOTIFICATION_CHANNELS: List[str] = ["email", "database"]
    
    # Validate URLs are properly formatted
    @validator("USER_SERVICE_URL", pre=True)
    def validate_service_urls(cls, v):
        if isinstance(v, str) and not v.startswith(("http://", "https://")):
            return f"http://{v}"
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Create global settings object
settings = Settings()