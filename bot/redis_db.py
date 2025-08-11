import os
import redis.asyncio as redis

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "devpass123")

# Redis client (async mode)
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=False 
)

async def set_processing_status(is_processing: bool):
    """
    Sets the global processing status in Redis.
    """
    await redis_client.set("processing_status", str(is_processing))

async def get_processing_status() -> bool:
    """
    Gets the global processing status from Redis.
    """
    status_bytes = await redis_client.get("processing_status")
    if status_bytes is None:
        return False  # Default to False if the key doesn't exist
    return status_bytes.decode('utf-8').lower() == 'true'