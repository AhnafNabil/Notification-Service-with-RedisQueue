import logging
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete, and_
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.models.notification import (
    Notification, NotificationCreate, NotificationResponse, NotificationSummary,
    NotificationPreference, NotificationPreferenceCreate, NotificationPreferenceUpdate, 
    NotificationPreferenceResponse
)
from app.db.postgresql import get_db
from app.services.user_service import user_service
from app.api.dependencies import get_current_user

# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=List[NotificationResponse])
async def get_notifications(
    user_id: str = Query(..., description="User ID to get notifications for"),
    skip: int = Query(0, ge=0, description="Number of notifications to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max number of notifications to return"),
    status: Optional[str] = Query(None, description="Filter by status"),
    type: Optional[str] = Query(None, description="Filter by notification type"),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get notifications for a user with optional filtering.
    """
    # Build query
    query = select(Notification).where(Notification.user_id == user_id)
    
    if status:
        query = query.where(Notification.status == status)
    
    if type:
        query = query.where(Notification.type == type)
    
    # Add ordering and pagination
    query = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    return notifications


@router.get("/unread", response_model=NotificationSummary)
async def get_notification_count(
    user_id: str = Query(..., description="User ID to get notification count for"),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get notification count summary for a user.
    """
    # Get total notifications
    total_query = select(Notification).where(Notification.user_id == user_id)
    total_result = await db.execute(total_query)
    total = len(total_result.scalars().all())
    
    # Get unread notifications
    unread_query = select(Notification).where(
        Notification.user_id == user_id,
        Notification.read_at == None
    )
    unread_result = await db.execute(unread_query)
    unread = len(unread_result.scalars().all())
    
    return {"total": total, "unread": unread}


@router.post("/mark-read/{notification_id}", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: int = Path(..., description="The notification ID to mark as read"),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Mark a notification as read.
    """
    # Get the notification
    result = await db.execute(select(Notification).where(Notification.id == notification_id))
    notification = result.scalars().first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification with ID {notification_id} not found"
        )
    
    # Mark as read
    notification.read_at = datetime.utcnow()
    notification.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(notification)
    
    return notification


@router.post("/mark-all-read", response_model=Dict[str, Any])
async def mark_all_notifications_read(
    user_id: str = Query(..., description="User ID to mark all notifications as read for"),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Mark all notifications as read for a user.
    """
    now = datetime.utcnow()
    
    # Update all unread notifications
    update_stmt = (
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.read_at == None
        )
        .values(
            read_at=now,
            updated_at=now
        )
    )
    
    result = await db.execute(update_stmt)
    await db.commit()
    
    return {"marked_read": result.rowcount}


@router.get("/preferences", response_model=List[NotificationPreferenceResponse])
async def get_notification_preferences(
    user_id: str = Query(..., description="User ID to get preferences for"),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get notification preferences for a user.
    """
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    preferences = result.scalars().all()
    
    return preferences


@router.post("/preferences", response_model=NotificationPreferenceResponse, status_code=201)
async def create_notification_preference(
    preference: NotificationPreferenceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Create a new notification preference.
    """
    # Check if preference already exists
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == preference.user_id,
            NotificationPreference.channel == preference.channel
        )
    )
    existing = result.scalars().first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Preference for channel {preference.channel} already exists for this user"
        )
    
    # Create preference
    db_preference = NotificationPreference(**preference.dict())
    
    db.add(db_preference)
    await db.commit()
    await db.refresh(db_preference)
    
    return db_preference


@router.put("/preferences/{preference_id}", response_model=NotificationPreferenceResponse)
async def update_notification_preference(
    preference_id: int,
    preference_update: NotificationPreferenceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Update a notification preference.
    """
    # Get the preference
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.id == preference_id)
    )
    db_preference = result.scalars().first()
    
    if not db_preference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preference with ID {preference_id} not found"
        )
    
    # Update with provided values
    update_data = preference_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_preference, key, value)
    
    await db.commit()
    await db.refresh(db_preference)
    
    return db_preference


@router.delete("/preferences/{preference_id}", status_code=204)
async def delete_notification_preference(
    preference_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Delete a notification preference.
    """
    # Get the preference
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.id == preference_id)
    )
    db_preference = result.scalars().first()
    
    if not db_preference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preference with ID {preference_id} not found"
        )
    
    # Delete the preference
    await db.delete(db_preference)
    await db.commit()
    
    return None


@router.post("/test", response_model=Dict[str, Any])
async def send_test_notification(
    user_id: str = Query(..., description="User ID to send test notification to"),
    channel: str = Query("email", description="Notification channel to test"),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Send a test notification to verify notification preferences.
    """
    # Check if preference exists
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.channel == channel
        )
    )
    preference = result.scalars().first()
    
    if not preference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No preference found for channel {channel}"
        )
    
    # Create a test notification
    test_notification = Notification(
        user_id=user_id,
        type="test",
        channel=channel,
        subject="Test Notification",
        content=f"This is a test notification sent to verify your {channel} notification preference.",
        status="pending",
        data={"test": True}
    )
    
    db.add(test_notification)
    await db.commit()
    
    return {"message": "Test notification created successfully", "notification_id": test_notification.id}