from dotenv import load_dotenv
load_dotenv()

import asyncio
import os
import logging
import requests
from typing import Optional

from ocr import extract_pdf
from redis_db import (
    redis_client,
    REDIS_HOST,
    REDIS_PORT,
    set_processing_status,
    get_processing_status
)

# ---------------- CONFIG GENERAL ----------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Redis listener config
OUTPUT_DIR = "extracted_markdown_files_temp"
METADATA_KEY_PATTERN = "pdf:meta:*"
FILENAME_INDEX_KEY = "md:filename_to_id"
POLLING_INTERVAL = 5
LOCK_TIMEOUT = 600
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Status listener config
API_RELOAD_URL = os.getenv("RELOAD_URL", "http://localhost:8001/reload-docs")

# ---------------- FUNCIONES REDIS LISTENER ----------------
async def acquire_lock(lock_key: str, timeout: int) -> bool:
    return await redis_client.set(lock_key, "locked", nx=True, ex=timeout)

async def release_lock(lock_key: str):
    await redis_client.delete(lock_key)

async def process_pdf_from_redis(file_id: str):
    lock_key = f"lock:ocr:{file_id}"
    if not await acquire_lock(lock_key, LOCK_TIMEOUT):
        logger.info(f"File {file_id} is already being processed by another worker. Skipping.")
        return
    
    logger.info(f"Acquired lock for file ID: {file_id}. Starting processing...")
    temp_pdf_path: Optional[str] = None
    
    try:
        content_key = f"pdf:content:{file_id}"
        meta_key = f"pdf:meta:{file_id}"
        markdown_hash_key = f"md:content:{file_id}"
        
        pdf_content = await redis_client.get(content_key)
        metadata = await redis_client.hgetall(meta_key)
        
        if not pdf_content or not metadata:
            logger.warning(f"File ID {file_id} has missing content or metadata. Skipping.")
            return

        original_filename = metadata.get(b'original_filename', b'unknown').decode('utf-8')
        temp_pdf_path = os.path.join(OUTPUT_DIR, f"{file_id}.pdf")
        with open(temp_pdf_path, 'wb') as f:
            f.write(pdf_content)

        # Ejecutar OCR en un hilo para no bloquear el event loop
        logger.info(f"Starting OCR for file: {original_filename}")
        markdown_content = await asyncio.to_thread(extract_pdf, dir=temp_pdf_path)
        logger.info(f"OCR completed for file: {original_filename}")
        
        markdown_data = {
            "content": markdown_content.encode('utf-8'),
            "original_filename": original_filename.encode('utf-8')
        }
        await redis_client.hset(markdown_hash_key, mapping=markdown_data)
        await redis_client.hset(FILENAME_INDEX_KEY, original_filename, file_id)
        await redis_client.delete(content_key)
        await redis_client.delete(meta_key)

    except Exception as e:
        logger.error(f"Error processing file ID {file_id}: {e}")
    finally:
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
        await release_lock(lock_key)

async def redis_listener():
    logger.info(f"Starting Redis listener service. Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")
    while True:
        try:
            keys = await redis_client.keys(METADATA_KEY_PATTERN)
            if keys:
                if await get_processing_status():
                    await set_processing_status(False)
                tasks = [process_pdf_from_redis(key.decode('utf-8').split(':')[-1]) for key in keys]
                await asyncio.gather(*tasks)

                remaining_keys = await redis_client.keys(METADATA_KEY_PATTERN)
                if not remaining_keys and not await get_processing_status():
                    await set_processing_status(True)
            else:
                if not await get_processing_status():
                    await set_processing_status(True)
                
            await asyncio.sleep(POLLING_INTERVAL)
        except Exception as e:
            logger.error(f"Error in Redis listener loop: {e}")
            await asyncio.sleep(POLLING_INTERVAL)

# ---------------- FUNCIONES STATUS LISTENER ----------------
async def status_listener():
    logger.info("Starting status listener service...")
    last_status = await get_processing_status()
    logger.info(f"Initial processing status is: {last_status}")

    while True:
        try:
            current_status = await get_processing_status()
            if not last_status and current_status:
                logger.info("Processing status changed to True. Notifying API to reload documents...")
                try:
                    response = requests.post(API_RELOAD_URL)
                    response.raise_for_status()
                    logger.info(f"API notification successful: {response.json().get('message')}")
                except requests.exceptions.RequestException as e:
                    logger.error(f"Error al notificar a la API: {e}")
            
            last_status = current_status
            await asyncio.sleep(POLLING_INTERVAL)
        except Exception as e:
            logger.error(f"Error in status listener loop: {e}")
            await asyncio.sleep(POLLING_INTERVAL)

# ---------------- MAIN ----------------
async def main():
    await asyncio.gather(
        redis_listener(),
        status_listener()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service stopped by user.")
