import os
import redis.asyncio as redis
from pathlib import Path
from schemas.File import FileUploadError
from fastapi import UploadFile
from typing import Dict
import uuid

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "devpass123")

# Redis client (async mode)
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=False  # Store as bytes
)

# A small schema of how data is stored in Redis:
# PDF Content:
# Key: pdf:content:{file_id}
# Value: The binary content of the PDF file (bytes)
#
# PDF Metadata:
# Key: pdf:meta:{file_id}
# Value: A Redis Hash containing metadata
#   - id: The unique file ID (string)
#   - original_filename: The original sanitized filename (string)
#   - content_type: The MIME type of the file (string)
#   - size_bytes: The size of the file in bytes (integer)

async def save_pdf_to_redis(file_id: str, file_content: bytes, metadata: Dict):
    """
    Saves PDF content and its metadata to Redis using a transaction.
    """
    content_key = f"pdf:content:{file_id}"
    meta_key = f"pdf:meta:{file_id}"

    try:
        # Save content and metadata to Redis in a single transaction
        async with redis_client.pipeline(transaction=True) as pipe:
            pipe.set(content_key, file_content)
            pipe.hset(meta_key, mapping=metadata)
            await pipe.execute()
    except Exception as e:
        raise FileUploadError(f"Error saving file to Redis: {str(e)}")

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