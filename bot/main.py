from dotenv import load_dotenv
load_dotenv()

import asyncio
import os
import logging
from typing import Optional

from ocr import extract_pdf
from redis_db import redis_client, REDIS_HOST, REDIS_PORT, set_processing_status
from redis_db import get_processing_status

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
# Temporary directory for PDFs
OUTPUT_DIR = "extracted_markdown_files_temp"
# Redis key pattern for PDF metadata
METADATA_KEY_PATTERN = "pdf:meta:*"
# Key for the filename index (maps filename to file_id)
FILENAME_INDEX_KEY = "md:filename_to_id"
# Polling interval in seconds to check for new keys
POLLING_INTERVAL = 5
# Lock timeout in seconds (10 minutes)
LOCK_TIMEOUT = 600

# Ensure the temporary output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)
logger.info(f"Temporary directory '{OUTPUT_DIR}' ensured to exist.")

async def acquire_lock(lock_key: str, timeout: int) -> bool:
    """
    Attempts to acquire a lock in Redis using SETNX with a timeout.
    Returns True if the lock was acquired, False otherwise.
    """
    return await redis_client.set(lock_key, "locked", nx=True, ex=timeout)

async def release_lock(lock_key: str):
    """
    Releases a lock by deleting its key.
    """
    await redis_client.delete(lock_key)

async def process_pdf_from_redis(file_id: str):
    """
    Fetches a PDF from Redis, converts it to Markdown, and saves it to Redis
    with its metadata. It uses a Redis lock to ensure only one worker processes the file.
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
        markdown_hash_key = f"md:content:{file_id}"
        
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
        
        # 5. Save the Markdown and metadata to a Redis Hash
        markdown_data = {
            "content": markdown_content.encode('utf-8'),
            "original_filename": original_filename.encode('utf-8')
        }
        await redis_client.hset(markdown_hash_key, mapping=markdown_data)
        logger.info(f"Successfully saved Markdown and metadata to Redis Hash: {markdown_hash_key}")

        # 6. Create/update the filename index
        await redis_client.hset(FILENAME_INDEX_KEY, original_filename, file_id)
        logger.info(f"Updated filename index for '{original_filename}' -> '{file_id}'")

        # 7. Successful completion: Remove the original PDF files from Redis
        await redis_client.delete(content_key)
        await redis_client.delete(meta_key)
        logger.info(f"Successfully deleted original PDF and metadata from Redis for file ID: {file_id}")

    except Exception as e:
        logger.error(f"Error processing file ID {file_id}: {e}")
    finally:
        # 8. Clean up the temporary PDF file and release the lock
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
            logger.info(f"Cleaned up temporary PDF file: {temp_pdf_path}")
        
        await release_lock(lock_key)
        logger.info(f"Released lock for file ID: {file_id}")

async def redis_listener():
    """
    Main asynchronous function that listens for new PDF files in Redis.
    It checks for unprocessed files and, after processing, verifies if any
    files remain to decide the final processing status.
    """
    logger.info(f"Starting Redis listener service. Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")
    
    while True:
        try:
            # 1. Check for any pending files
            keys = await redis_client.keys(METADATA_KEY_PATTERN)
            
            if keys:
                logger.info(f"Found {len(keys)} pending files to process.")
                # Si hay archivos, el estado ya debe ser False, pero lo confirmamos.
                if await get_processing_status():
                    await set_processing_status(False)
                    logger.info("Processing status manually set to False as new files were found.")

                tasks = [process_pdf_from_redis(key.decode('utf-8').split(':')[-1]) for key in keys]
                await asyncio.gather(*tasks)

                # 2. After processing, re-check if there are any files left
                remaining_keys = await redis_client.keys(METADATA_KEY_PATTERN)
                if not remaining_keys and not await get_processing_status():
                    # If no keys are left and the status is still False, the work is done.
                    await set_processing_status(True)
                    logger.info("All files processed. Setting processing status to True.")
            else:
                # If there are no keys to begin with, ensure the status is True
                if not await get_processing_status():
                    await set_processing_status(True)
                    logger.info("No files found. Setting processing status to True.")
                
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