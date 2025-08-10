from dotenv import load_dotenv
load_dotenv()

import asyncio
import os
import logging
from ocr import extract_pdf
from redis_db import redis_client, REDIS_HOST, REDIS_PORT
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
OUTPUT_DIR = "extracted_markdown_files"
METADATA_KEY_PATTERN = "pdf:meta:*"
POLLING_INTERVAL = 5
LOCK_TIMEOUT = 600  # 10 minutes in seconds

# Ensure the output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)
logger.info(f"Output directory '{OUTPUT_DIR}' ensured to exist.")

async def acquire_lock(lock_key: str, timeout: int) -> bool:
    """
    Attempts to acquire a lock in Redis using SETNX with a timeout.
    Returns True if the lock was acquired, False otherwise.
    """
    # Use redis_client.set with nx=True and ex=timeout for atomic lock acquisition
    return await redis_client.set(lock_key, "locked", nx=True, ex=timeout)

async def release_lock(lock_key: str):
    """
    Releases a lock by deleting its key.
    """
    await redis_client.delete(lock_key)

async def process_pdf_from_redis(file_id: str):
    """
    Fetches a PDF from Redis, converts it to Markdown, and saves it to a file.
    It uses a Redis lock to ensure only one worker processes the file.
    """
    lock_key = f"lock:ocr:{file_id}"
    
    # 1. Attempt to acquire a lock for this file
    if not await acquire_lock(lock_key, LOCK_TIMEOUT):
        logger.info(f"File {file_id} is already being processed by another worker. Skipping.")
        return
    
    logger.info(f"Acquired lock for file ID: {file_id}. Starting processing...")
    
    temp_pdf_path: Optional[str] = None
    
    try:
        content_key = f"pdf:content:{file_id}"
        meta_key = f"pdf:meta:{file_id}"
        
        # 2. Fetch PDF content and metadata
        pdf_content = await redis_client.get(content_key)
        metadata = await redis_client.hgetall(meta_key)
        
        if not pdf_content or not metadata:
            logger.warning(f"File ID {file_id} has missing content or metadata in Redis. Releasing lock and skipping.")
            await release_lock(lock_key)
            return

        original_filename = metadata.get(b'original_filename', b'unknown').decode('utf-8')
        logger.info(f"Fetched file '{original_filename}' from Redis.")
        
        # 3. Save the PDF content to a temporary file for OCR
        temp_pdf_path = os.path.join(OUTPUT_DIR, f"{file_id}.pdf")
        with open(temp_pdf_path, 'wb') as f:
            f.write(pdf_content)
        logger.info(f"Saved PDF to temporary path: {temp_pdf_path}")

        # 4. Use the OCR service to convert the PDF to Markdown
        markdown_content = extract_pdf(dir=temp_pdf_path)
        
        # 5. Save the Markdown content to a file
        markdown_filename = f"{os.path.splitext(original_filename)[0]}_{file_id}.md"
        markdown_path = os.path.join(OUTPUT_DIR, markdown_filename)
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        logger.info(f"Successfully converted and saved Markdown to: {markdown_path}")
        
        # 6. --- SUCCESSFUL COMPLETION: REMOVE THE ORIGINAL FILES FROM REDIS ---
        await redis_client.delete(content_key)
        await redis_client.delete(meta_key)
        logger.info(f"Successfully deleted original PDF and metadata from Redis for file ID: {file_id}")

    except Exception as e:
        logger.error(f"Error processing file ID {file_id}: {e}")
        # The lock will expire eventually, but we can't remove the original files
    finally:
        # 7. Clean up the temporary PDF file and release the lock
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
            logger.info(f"Cleaned up temporary PDF file: {temp_pdf_path}")
        
        await release_lock(lock_key)
        logger.info(f"Released lock for file ID: {file_id}")

async def redis_listener():
    """
    Main asynchronous function that listens for new PDF files in Redis.
    """
    logger.info(f"Starting Redis listener service. Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")
    
    while True:
        try:
            keys = await redis_client.keys(METADATA_KEY_PATTERN)
            
            for key in keys:
                file_id = key.decode('utf-8').split(':')[-1]
                # A file key exists, so we try to process it
                asyncio.create_task(process_pdf_from_redis(file_id))
            
            await asyncio.sleep(POLLING_INTERVAL)
            
        except Exception as e:
            logger.error(f"An error occurred in the listener loop: {e}")
            await asyncio.sleep(POLLING_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(redis_listener())
    except KeyboardInterrupt:
        logger.info("Service stopped by user.")
    except Exception as e:
        logger.critical(f"A fatal error occurred: {e}")