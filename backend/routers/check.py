from fastapi import APIRouter
from database.redis import get_processing_status, set_processing_status

router = APIRouter(prefix="/check", tags=["Data Check"])

@router.get("/status", tags=["Data Check"])
async def check_status():
    """
    Endpoint to check the status of the data processing service from Redis.
    """
    status = await get_processing_status()
    return {"status": status}

@router.post("/start", tags=["Data Check"])
async def change_status():
    """
    Endpoint to manually start the data processing service by setting the status to True.
    """
    await set_processing_status(True)
    return {"status": True}