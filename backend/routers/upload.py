import os
import logging
from pathlib import Path
from typing import List

import aiofiles
from fastapi import APIRouter, File, HTTPException, UploadFile, status

# Configure logging
logger = logging.getLogger(__name__)

# Constants
UPLOAD_DIRECTORY = Path(os.getenv("UPLOAD_DIRECTORY", "data"))
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
CHUNK_SIZE = 1024 * 1024  # 1MB chunks
ALLOWED_CONTENT_TYPES = {"application/pdf"}

# Ensure upload directory exists
UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)

# Router for file upload operations
router = APIRouter(prefix="/files", tags=["Files"])


class FileUploadError(Exception):
    """Custom exception for file upload errors"""
    pass


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


@router.post(
    "/upload-pdfs",
    summary="Upload one or multiple PDF files",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Files uploaded successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Successfully uploaded 2 PDF files",
                        "uploaded_files": ["document1.pdf", "document2.pdf"],
                        "total_files": 2
                    }
                }
            }
        },
        400: {"description": "Invalid file type or missing filename"},
        413: {"description": "File too large"},
        500: {"description": "Internal server error during file upload"}
    }
)
async def upload_multiple_pdfs(
    files: List[UploadFile] = File(..., description="List of PDF files to upload")
) -> dict:
    """
    Upload one or more PDF files to the server.

    This endpoint is designed to be efficient and non-blocking:
    - **Asynchronous processing**: Frees the main server thread to handle other requests
    - **Chunked reading**: Reads and writes files in chunks to handle large files without exhausting RAM
    - **Type validation**: Rejects files that don't have 'application/pdf' Content-Type
    - **Size validation**: Prevents upload of files exceeding maximum size limit
    - **Security**: Sanitizes filenames to prevent path traversal attacks

    **Returns**:
    - JSON object confirming the number of uploaded files and their names
    - 400 error if any file is not a valid PDF or missing filename
    - 413 error if any file exceeds size limit
    - 500 error if there's an issue saving any file
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided"
        )

    uploaded_filenames = []
    failed_uploads = []

    for file in files:
        try:
            # Validate file
            await validate_pdf_file(file)
            
            # Sanitize filename
            sanitized_filename = sanitize_filename(file.filename)
            destination_path = UPLOAD_DIRECTORY / sanitized_filename
            
            # Handle filename conflicts by appending a number
            counter = 1
            original_stem = destination_path.stem
            original_suffix = destination_path.suffix
            
            while destination_path.exists():
                new_filename = f"{original_stem}_{counter}{original_suffix}"
                destination_path = UPLOAD_DIRECTORY / new_filename
                counter += 1
            
            # Save file
            await save_file_async(file, destination_path)
            uploaded_filenames.append(destination_path.name)
            
        except HTTPException:
            # Re-raise HTTP exceptions (validation errors)
            raise
        except FileUploadError as e:
            # Handle file saving errors
            failed_uploads.append({"filename": file.filename, "error": str(e)})
            logger.error(f"Upload failed for {file.filename}: {str(e)}")
        except Exception as e:
            # Handle unexpected errors
            error_msg = f"Unexpected error processing file '{file.filename}': {str(e)}"
            failed_uploads.append({"filename": file.filename, "error": error_msg})
            logger.error(error_msg)
        finally:
            # Always close the file to free resources
            if hasattr(file, 'file'):
                await file.close()

    # If some files failed but others succeeded, return partial success
    if failed_uploads and uploaded_filenames:
        logger.warning(f"Partial upload success: {len(uploaded_filenames)} succeeded, {len(failed_uploads)} failed")
        return {
            "message": f"Partially successful: {len(uploaded_filenames)} files uploaded, {len(failed_uploads)} failed",
            "uploaded_files": uploaded_filenames,
            "failed_uploads": failed_uploads,
            "total_files": len(uploaded_filenames)
        }
    
    # If all files failed
    if failed_uploads:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "All file uploads failed",
                "failed_uploads": failed_uploads
            }
        )

    # All files succeeded
    logger.info(f"Successfully uploaded {len(uploaded_filenames)} files")
    return {
        "message": f"Successfully uploaded {len(uploaded_filenames)} PDF files",
        "uploaded_files": uploaded_filenames,
        "total_files": len(uploaded_filenames)
    }