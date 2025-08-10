from dotenv import load_dotenv
load_dotenv()

import asyncio
import os
import logging
from ocr import extract_pdf
from redis_db import redis_client, REDIS_HOST, REDIS_PORT

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
# Directory to save the extracted markdown files
OUTPUT_DIR = "extracted_markdown_files"
# The pattern for the Redis keys used for PDF metadata
METADATA_KEY_PATTERN = "pdf:meta:*"
# Polling interval in seconds to check for new keys
POLLING_INTERVAL = 5 

# Set to store processed file IDs to avoid reprocessing
processed_files = set()

# Ensure the output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)
logger.info(f"Output directory '{OUTPUT_DIR}' ensured to exist.")

async def process_pdf_from_redis(file_id: str):
    """
    Fetches a PDF from Redis, converts it to Markdown, and saves it to a file.
    """
    logger.info(f"Processing new file with ID: {file_id}")
    
    content_key = f"pdf:content:{file_id}"
    meta_key = f"pdf:meta:{file_id}"
    
    # 1. Fetch PDF content and metadata from Redis
    try:
        pdf_content = await redis_client.get(content_key)
        metadata = await redis_client.hgetall(meta_key)
        
        if not pdf_content or not metadata:
            logger.warning(f"File ID {file_id} has missing content or metadata in Redis. Skipping.")
            return

        original_filename = metadata.get(b'original_filename', b'unknown').decode('utf-8')
        logger.info(f"Fetched file '{original_filename}' from Redis.")
        
        # 2. Save the PDF content to a temporary file
        # The extract_pdf function expects a file path or URL
        temp_pdf_path = os.path.join(OUTPUT_DIR, f"{file_id}.pdf")
        with open(temp_pdf_path, 'wb') as f:
            f.write(pdf_content)
        logger.info(f"Saved PDF to temporary path: {temp_pdf_path}")

        # 3. Use the OCR service to convert the PDF to Markdown
        markdown_content = extract_pdf(dir=temp_pdf_path)
        
        # 4. Save the Markdown content to a file
        markdown_filename = f"{os.path.splitext(original_filename)[0]}_{file_id}.md"
        markdown_path = os.path.join(OUTPUT_DIR, markdown_filename)
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        logger.info(f"Successfully converted and saved Markdown to: {markdown_path}")

    except Exception as e:
        logger.error(f"Error processing file ID {file_id}: {e}")
    finally:
        # 5. Clean up the temporary PDF file
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
            logger.info(f"Cleaned up temporary PDF file: {temp_pdf_path}")
            
    processed_files.add(file_id)

async def redis_listener():
    """
    Main asynchronous function that listens for new PDF files in Redis.
    """
    logger.info(f"Starting Redis listener service. Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")
    
    # Initial scan to catch any files already in Redis before the listener started
    initial_keys = await redis_client.keys(METADATA_KEY_PATTERN)
    initial_file_ids = [key.decode('utf-8').split(':')[-1] for key in initial_keys]
    
    if initial_file_ids:
        logger.info(f"Found {len(initial_file_ids)} existing files on startup. Processing them...")
        for file_id in initial_file_ids:
            if file_id not in processed_files:
                asyncio.create_task(process_pdf_from_redis(file_id))
    
    while True:
        try:
            # Poll Redis for new keys matching the pattern
            # Note: This is a simple polling approach. For a high-throughput system,
            # a Pub/Sub model might be more efficient.
            keys = await redis_client.keys(METADATA_KEY_PATTERN)
            
            for key in keys:
                file_id = key.decode('utf-8').split(':')[-1]
                if file_id not in processed_files:
                    logger.info(f"Detected new file key: {file_id}")
                    # Create a task to process the file concurrently
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