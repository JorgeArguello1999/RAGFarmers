import os
import logging
import uuid 
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from database.redis import save_pdf_to_redis, redis_client
from schemas.File import FileUploadError

from utils.file import sanitize_filename
from utils.file import validate_pdf_file

# Configure logging
logger = logging.getLogger(__name__)

# Router for file upload operations
router = APIRouter(prefix="/files", tags=["Files"])


@router.post(
    "/upload-pdfs", 
    summary="Upload one or multiple PDF files to Redis with a unique ID",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Files were successfully stored in Redis.",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Successfully stored 2 PDF files in Redis.",
                        "uploaded_files": [
                            {"file_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d", "original_filename": "document1.pdf"},
                            {"file_id": "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e", "original_filename": "report.pdf"}
                        ],
                        "total_files": 2
                    }
                }
            }
        },
        400: {"description": "Invalid file type or missing file."},
        500: {"description": "Internal server error during file upload."}
    }
)
async def upload_multiple_pdfs_to_redis(
    files: List[UploadFile] = File(..., description="List of PDF files to upload.")
) -> dict:
    """
    Uploads one or more PDF files, assigns a unique ID to each, and stores them in Redis.

    This endpoint operates asynchronously and handles files efficiently:
    - **Unique ID**: Each file is assigned a UUID v4 for robust identification.
    - **Atomic Operations**: File content and metadata are stored in a single Redis transaction.
    - **Metadata Storage**: Saves the original filename and content type alongside the file.
    - **Security**: Sanitizes filenames before storing them as metadata.

    **Returns**:
    - A JSON object with the unique IDs and original filenames of the stored files.
    - 400 error for invalid files.
    - 500 error if storage fails.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files were provided."
        )

    uploaded_files_info = []
    failed_uploads = []

    for file in files:
        try:
            # 1. Validate that the file is a PDF
            await validate_pdf_file(file)

            # 2. Generate a unique identifier for the file
            file_id = str(uuid.uuid4())
            sanitized_filename = sanitize_filename(file.filename)

            # 3. Read file content
            # The file must be read into memory to be sent to Redis
            await file.seek(0)
            file_content = await file.read()

            # 4. Prepare metadata
            metadata = {
                "id": file_id,
                "original_filename": sanitized_filename,
                "content_type": file.content_type,
                "size_bytes": len(file_content)
            }

            # 5. Save content and metadata to Redis using the new function
            await save_pdf_to_redis(file_id, file_content, metadata)
            
            uploaded_files_info.append({"file_id": file_id, "original_filename": sanitized_filename})

        except HTTPException:
            # Re-raise validation errors
            raise
        except FileUploadError as e:
            # Handle specific Redis upload errors
            error_msg = f"Error storing file '{file.filename}' in Redis: {str(e)}"
            failed_uploads.append({"filename": file.filename, "error": error_msg})
            logger.error(error_msg)
        except Exception as e:
            # Handle any other unexpected errors
            error_msg = f"An unexpected error occurred with file '{file.filename}': {str(e)}"
            failed_uploads.append({"filename": file.filename, "error": error_msg})
            logger.error(error_msg)
        finally:
            # Always close the file to release resources
            await file.close()

    # Handle partial success
    if failed_uploads and uploaded_files_info:
        logger.warning(f"Partial upload: {len(uploaded_files_info)} succeeded, {len(failed_uploads)} failed.")
        return {
            "message": f"Partially successful: {len(uploaded_files_info)} files stored, {len(failed_uploads)} failed.",
            "uploaded_files": uploaded_files_info,
            "failed_uploads": failed_uploads
        }

    # Handle total failure
    if failed_uploads:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "All file uploads to Redis failed.",
                "failed_uploads": failed_uploads
            }
        )

    # Handle total success
    logger.info(f"Successfully stored {len(uploaded_files_info)} files in Redis.")
    return {
        "message": f"Successfully stored {len(uploaded_files_info)} PDF files in Redis.",
        "uploaded_files": uploaded_files_info,
        "total_files": len(uploaded_files_info)
    }