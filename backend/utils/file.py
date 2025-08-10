from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pathlib import Path
import logging

from schemas.File import FileUploadError

import aiofiles
import os 

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
CHUNK_SIZE = 1024 * 1024  # 1MB chunks
ALLOWED_CONTENT_TYPES = {"application/pdf"}
logger = logging.getLogger(__name__)

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal attacks and invalid characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Get basename to prevent path traversal
    clean_name = os.path.basename(filename)
    
    # Replace any remaining problematic characters
    invalid_chars = '<>:"|?*'
    for char in invalid_chars:
        clean_name = clean_name.replace(char, '_')
    
    return clean_name


async def validate_pdf_file(file: UploadFile) -> None:
    """
    Validate that the uploaded file is a valid PDF.
    
    Args:
        file: The uploaded file to validate
        
    Raises:
        HTTPException: If file validation fails
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required"
        )
    
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type '{file.content_type}' for file '{file.filename}'. Only PDF files are allowed."
        )
    
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File '{file.filename}' is too large. Maximum size allowed: {MAX_FILE_SIZE // (1024*1024)}MB"
        )


async def save_file_async(file: UploadFile, destination: Path) -> None:
    """
    Save uploaded file to destination path asynchronously.
    
    Args:
        file: The uploaded file to save
        destination: Path where the file will be saved
        
    Raises:
        FileUploadError: If file saving fails
    """
    try:
        async with aiofiles.open(destination, 'wb') as out_file:
            await file.seek(0)  # Ensure we start from the beginning
            
            while chunk := await file.read(CHUNK_SIZE):
                await out_file.write(chunk)
                
        logger.info(f"Successfully saved file: {destination}")
        
    except Exception as e:
        logger.error(f"Failed to save file {file.filename}: {str(e)}")
        raise FileUploadError(f"Could not save file '{file.filename}': {str(e)}")