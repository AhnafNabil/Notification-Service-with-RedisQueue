import json
import logging
import redis.asyncio as redis
from typing import Any, Dict, List, Optional, Callable, Awaitable

from app.core.config import settings

logger = logging.getLogger(__name__)

class RedisClient:
    """Client for interacting with Redis."""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.client = None
        self.pubsub = None
        self._running = False
    
    async def connect(self):
        """Establish connection to Redis."""
        if self.client is None:
            try:
                self.client = await redis.from_url(self.redis_url, decode_responses=True)
                self.pubsub = self.client.pubsub()
                logger.info("Connected to Redis")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {str(e)}")
                raise
    
    async def close(self):
        """Close the Redis connection."""
        if self.pubsub:
            await self.pubsub.close()
        
        if self.client:
            await self.client.close()
            logger.info("Closed Redis connection")
    
    async def subscribe(self, channel: str, handler: Callable[[Dict[str, Any]], Awaitable[None]]):
        """Subscribe to a Redis channel with a message handler."""
        if not self.client:
            await self.connect()
        
        await self.pubsub.subscribe(channel)
        logger.info(f"Subscribed to channel: {channel}")
        
        self._running = True
        while self._running:
            message = await self.pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message['type'] == 'message':
                try:
                    # Parse JSON data
                    data = json.loads(message['data'])
                    
                    # Call the handler with the parsed data
                    await handler(data)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse message data: {message['data']}")
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
    
    async def get_stream_messages(self, stream_name: str, count: int = 10, last_id: str = '0-0') -> List[Dict]:
        """Read messages from a Redis stream."""
        if not self.client:
            await self.connect()
        
        try:
            # Read messages from the stream
            messages = await self.client.xread({stream_name: last_id}, count=count, block=0)
            
            # Process and return messages
            result = []
            for stream, stream_messages in messages:
                for message_id, fields in stream_messages:
                    result.append({
                        'id': message_id,
                        'data': fields
                    })
            
            return result
        except Exception as e:
            logger.error(f"Error reading from stream {stream_name}: {str(e)}")
            return []
    
    async def acknowledge_message(self, stream_name: str, group_name: str, message_id: str):
        """Acknowledge a message in a consumer group."""
        if not self.client:
            await self.connect()
        
        try:
            await self.client.xack(stream_name, group_name, message_id)
        except Exception as e:
            logger.error(f"Error acknowledging message {message_id}: {str(e)}")
    
    async def stop(self):
        """Stop the subscription loop."""
        self._running = False

# Create a singleton instance
redis_client = RedisClient(str(settings.REDIS_URL))