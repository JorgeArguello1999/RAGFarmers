from pydantic import BaseModel

class MessageRequest(BaseModel):
    message: str

class HistoryMessage(BaseModel):
    content: str
    type: str

