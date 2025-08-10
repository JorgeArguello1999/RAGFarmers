import os
import redis.asyncio as redis
from pathlib import Path
from schemas.File import FileUploadError
from fastapi import UploadFile

# Configuración de Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "devpass123")

# Cliente Redis (modo async)
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=False  # Guardar como bytes
)

async def save_file_to_redis(file: UploadFile, redis_key: str):
    """
    Save a file to Redis under the specified key.
    """
    try:
        file_data = b""
        while chunk := await file.read(1024 * 1024):  # 1MB por chunk
            file_data += chunk

        await redis_client.set(redis_key, file_data)

    except Exception as e:
        raise FileUploadError(f"Error saving file to Redis: {str(e)}")

async def key_exists(redis_key: str) -> bool:
    """
    Check if a key exists in Redis.
    """
    return await redis_client.exists(redis_key)
