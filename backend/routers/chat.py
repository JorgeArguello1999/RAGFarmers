import os
import sys
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, HTTPException, APIRouter

from schemas.Chat import MessageRequest, HistoryMessage

# Import the new LLM service module
from models.LLM_chatbot import (
    initialize_llm_workflow,
    reload_documents_context,
    chat_with_assistant_service,
    get_chat_history_service,
    reset_conversation_service,
)
from models.config import ContextoGeneral


app = APIRouter(prefix="/llm", tags=["LLM Chat"])

@app.on_event("startup")
async def startup_event():
    """Initializes the LLM and LangGraph workflow on application startup."""
    await initialize_llm_workflow()

@app.post("/reload-docs", summary="Reload all Markdown documents from Redis")
async def reload_documents() -> Dict[str, str]:
    """Recarga los documentos Markdown desde Redis y actualiza el contexto del LLM."""
    try:
        await reload_documents_context()
        return {"status": "success", "message": "Successfully reloaded documents."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat", summary="Send a message and get an assistant response")
async def chat_with_assistant(request: MessageRequest) -> Dict[str, str]:
    """Handles a single turn of the conversation."""
    try:
        response = await chat_with_assistant_service(request.message)
        return {"response": response}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/history", summary="Get the full conversation history")
async def get_chat_history() -> List[HistoryMessage]:
    """Retrieves all messages for the current conversation thread."""
    try:
        history = await get_chat_history_service()
        return [HistoryMessage(content=msg.content, type=msg.type) for msg in history]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/reset", summary="Reset the current conversation")
async def reset_conversation() -> Dict[str, str]:
    """Clears the conversation history for the current thread."""
    try:
        await reset_conversation_service()
        return {"status": "success", "message": "Conversation history has been reset."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))