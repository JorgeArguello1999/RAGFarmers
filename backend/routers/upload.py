import os
import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from schemas.File import FileUploadError

from utils.file import sanitize_filename
from utils.file import validate_pdf_file, save_file_async

# Configure logging
logger = logging.getLogger(__name__)

# Constants
UPLOAD_DIRECTORY = Path(os.getenv("UPLOAD_DIRECTORY", "data"))

# Ensure upload directory exists
UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)

# Router for file upload operations
router = APIRouter(prefix="/files", tags=["Files"])



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