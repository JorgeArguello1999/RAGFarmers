import os
import logging

from pathlib import Path
from fastapi import APIRouter

# Configure logging
logger = logging.getLogger(__name__)

# Router for file upload operations
router = APIRouter(prefix="", tags=["Home"])

# Routes at the root level
@router.get("", tags=["Home"])
async def root():
    """
    Check if the server is running
    """
    return {"status": "El servidor está en línea y respondiendo."}

