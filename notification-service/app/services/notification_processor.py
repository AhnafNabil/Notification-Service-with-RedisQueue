import json
import logging
import asyncio
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List

from app.core.config import settings
from app.db.postgresql import AsyncSessionLocal
from app.models.notification import Notification, NotificationPreference, NotificationTemplate
from app.services.redis_client import redis_client
from app.services.email_provider import email_provider
from app.services.user_service import user_service

logger = logging.getLogger(__name__)

class NotificationProcessor:
    """Processor for handling notifications."""
    
    def __init__(self):
        self.running = False
        self.batch_size = settings.NOTIFICATION_BATCH_SIZE
        self.processing_interval = settings.NOTIFICATION_PROCESSING_INTERVAL
    
    async def start(self):
        """Start the notification processor."""
        self.running = True
        
        # Start the Redis subscription for real-time notifications
        asyncio.create_task(self.listen_for_notifications())
        
        # Start the background processor for processing pending notifications
        asyncio.create_task(self.process_pending_notifications())
        
        logger.info("Notification processor started")
    
    async def stop(self):
        """Stop the notification processor."""
        self.running = False
        await redis_client.stop()
        logger.info("Notification processor stopped")
    
    async def listen_for_notifications(self):
        """Listen for notifications from Redis pub/sub."""
        channel = settings.NOTIFICATION_CHANNEL
        await redis_client.subscribe(channel, self.handle_notification)
    
    async def handle_notification(self, data: Dict[str, Any]):
        """Handle a notification received from Redis."""
        logger.info(f"Received notification: {data}")
        
        try:
            notification_type = data.get("type")
            
            if notification_type == "low_stock":
                await self.handle_low_stock_notification(data)
            else:
                logger.warning(f"Unknown notification type: {notification_type}")
        
        except Exception as e:
            logger.error(f"Error handling notification: {str(e)}")
    
    async def handle_low_stock_notification(self, data: Dict[str, Any]):
        """Handle a low stock notification and send directly to admin email."""
        product_id = data.get("product_id")
        product_name = data.get("product_name", product_id)
        current_quantity = data.get("current_quantity")
        threshold = data.get("threshold")
        
        if not product_id or current_quantity is None or threshold is None:
            logger.error(f"Invalid low stock notification data: {data}")
            return
        
        # Create a notification in the database
        notification_data = {
            "type": "low_stock",
            "channel": "database",  # Store in the database as system notification
            "subject": f"Low Stock Alert: {product_name}",
            "content": f"Product '{product_name}' is running low on stock. Current quantity: {current_quantity}, Threshold: {threshold}",
            "data": data,
            "status": "pending"
        }
        
        # Create a system-level notification in the database
        async with AsyncSessionLocal() as db:
            # Create a system notification
            system_notification = Notification(**notification_data)
            db.add(system_notification)
            await db.commit()
            await db.refresh(system_notification)
        
        # Send email directly to admin without checking preferences
        if settings.ADMIN_EMAIL:
            # Prepare email content
            html_content = f"""
            <h2>Low Stock Alert</h2>
            <p>Product <strong>{product_name}</strong> is running low on stock.</p>
            <ul>
                <li><strong>Product ID:</strong> {product_id}</li>
                <li><strong>Current Quantity:</strong> {current_quantity}</li>
                <li><strong>Threshold:</strong> {threshold}</li>
            </ul>
            <p>Please replenish the inventory as soon as possible.</p>
            """
            
            # Send email directly
            from app.services.email_provider import email_provider
            success = await email_provider.send_email(
                to_email=settings.ADMIN_EMAIL,
                subject=f"Low Stock Alert: {product_name}",
                html_content=html_content
            )
            
            if success:
                logger.info(f"Sent low stock email notification to admin for product {product_id}")
            else:
                logger.error(f"Failed to send low stock email notification to admin for product {product_id}")
        else:
            logger.warning("Admin email not configured. Cannot send low stock notification email.")
        
        logger.info(f"Processed low stock notification for product {product_id}")
    
    async def process_pending_notifications(self):
        """Process pending notifications periodically."""
        while self.running:
            try:
                # Process a batch of pending notifications
                async with AsyncSessionLocal() as db:
                    # Get pending notifications
                    result = await db.execute(
                        select(Notification)
                        .where(Notification.status == "pending")
                        .order_by(Notification.created_at)
                        .limit(self.batch_size)
                    )
                    pending = result.scalars().all()
                    
                    # Process each notification
                    for notification in pending:
                        await self.send_notification(db, notification)
                    
                    await db.commit()
            
            except Exception as e:
                logger.error(f"Error processing pending notifications: {str(e)}")
            
            # Wait for the next processing interval
            await asyncio.sleep(self.processing_interval)
    
    async def send_notification(self, db: AsyncSession, notification: Notification):
        """Send a notification through its channel."""
        try:
            # Update notification status to processing
            notification.status = "processing"
            notification.updated_at = datetime.utcnow()
            await db.commit()
            
            # Process based on channel
            channel = notification.channel
            success = False
            
            if channel == "email":
                # Get user email
                if notification.user_id:
                    # Find the user's email preference
                    result = await db.execute(
                        select(NotificationPreference)
                        .where(
                            NotificationPreference.user_id == notification.user_id,
                            NotificationPreference.channel == "email"
                        )
                    )
                    preference = result.scalars().first()
                    
                    if preference and preference.email:
                        # Send email
                        success = await email_provider.send_email(
                            to_email=preference.email,
                            subject=notification.subject,
                            html_content=notification.content
                        )
            
            elif channel == "database":
                # Just mark as sent for database notifications
                success = True
            
            # Update notification status
            if success:
                notification.status = "sent"
                notification.sent_at = datetime.utcnow()
            else:
                notification.status = "failed"
                notification.error_message = "Failed to send notification"
            
            notification.updated_at = datetime.utcnow()
            await db.commit()
            
            logger.info(f"Processed notification {notification.id}: {notification.status}")
        
        except Exception as e:
            logger.error(f"Error sending notification {notification.id}: {str(e)}")
            notification.status = "failed"
            notification.error_message = str(e)
            notification.updated_at = datetime.utcnow()
            await db.commit()

# Create a singleton instance
notification_processor = NotificationProcessor()