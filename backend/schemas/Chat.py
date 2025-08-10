from pydantic import BaseModel
from pydantic import Optional

# Pydantic models for message validation
class ChatMessage(BaseModel):
    type: str = "user_message"
    content: str
    timestamp: Optional[float] = None

class SystemMessage(BaseModel):
    type: str = "system_message" 
    content: str
    timestamp: float
