
import os
import sys
import asyncio
from pathlib import Path
from typing import List, Dict, Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, BaseMessage
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Assuming src and redis_db.py are in the same directory as this script.
# You might need to adjust these imports if your file structure is different.
from src.config import ContextoGeneral
from src.redis_db import redis_client


# -------------------
# Paths
# -------------------
# The following path setup should be reviewed to ensure it correctly points to
# your source files.
try:
    MAIN_PATH = Path(sys.modules["__main__"].__file__).resolve().parent
    sys.path.append(str(MAIN_PATH / "src"))
    os.chdir(MAIN_PATH)
except (AttributeError, FileNotFoundError):
    # This block handles cases where the script is run in an interactive environment
    # or the path cannot be resolved.
    pass

# -------------------
# LLM y flujo
# -------------------
# Load environment variables
load_dotenv()
model = init_chat_model("gpt-4o-mini", model_provider="openai", temperature=0)

app = FastAPI()

# Pydantic model for the incoming message
class MessageRequest(BaseModel):
    message: str

# Pydantic model for a message in the history
class HistoryMessage(BaseModel):
    content: str
    type: str

# Global variables for the app state
app_llm = None
markdown_unido_global = None
memory = MemorySaver()
CONVERSATION_THREAD_ID = "conv_unica"
config = {"configurable": {"thread_id": CONVERSATION_THREAD_ID}}


async def get_all_markdown_docs():
    """Obtiene todos los contenidos Markdown desde Redis y los concatena."""
    md_keys = await redis_client.keys("md:content:*")
    if not md_keys:
        return None, None
    
    contenido_total = []
    nombres = []
    for key in md_keys:
        data = await redis_client.hgetall(key)
        markdown = data.get(b"content", b"").decode("utf-8")
        filename = data.get(b"original_filename", b"unknown").decode("utf-8")
        if markdown:
            contenido_total.append(f"# Documento: {filename}\n\n{markdown}")
            nombres.append(filename)
    markdown_unido = "\n\n---\n\n".join(contenido_total)
    return markdown_unido, nombres


def call_model(state: MessagesState):
    """
    Invokes the LLM with the current conversation state and the system prompt.
    This function is a node in the LangGraph workflow.
    """
    # The prompt is re-invoked with the latest state
    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", ContextoGeneral),
            ("system", "Documentos en Markdown:\n{markdown}"),
            MessagesPlaceholder(variable_name="messages"),
        ]
    ).partial(markdown=markdown_unido_global)
    
    prompt = prompt_template.invoke(state)
    response = model.invoke(prompt)
    return {"messages": response}


async def initialize_llm_workflow():
    """
    Initializes the LangGraph workflow with the latest documents.
    """
    global app_llm, markdown_unido_global

    markdown_unido, nombres = await get_all_markdown_docs()
    if not markdown_unido:
        print("No hay documentos Markdown en Redis.")
        markdown_unido_global = None
        app_llm = None
        return
    
    print(f"Documentos cargados desde Redis: {', '.join(nombres)}")
    print(f"Total de documentos: {len(nombres)}")
    markdown_unido_global = markdown_unido

    # Refactorizado: Se crea una nueva instancia de StateGraph cada vez.
    workflow = StateGraph(state_schema=MessagesState)
    workflow.add_edge(START, "model")
    workflow.add_node("model", call_model)
    app_llm = workflow.compile(checkpointer=memory)

    # Initializing the graph with an empty state
    try:
        # Check if the thread exists to avoid invoking the graph unnecessarily
        state = await app_llm.get_state(config)
        if not state:
            # If no history exists, initialize it with a clean state.
            await app_llm.acreate_checkpoint(config, {"messages": []})
        else:
            print("Conversation history found. Not resetting on reload.")
    except Exception as e:
        print(f"Error during initial graph invocation: {e}")

# -------------------
# FastAPI Endpoints
# -------------------
@app.on_event("startup")
async def startup_event():
    """
    Initializes the LLM and LangGraph workflow on application startup.
    """
    await initialize_llm_workflow()

@app.post("/reload-docs", summary="Reload all Markdown documents from Redis")
async def reload_documents() -> Dict[str, str]:
    """
    Recarga los documentos Markdown desde Redis y actualiza el contexto del LLM.
    """
    try:
        await initialize_llm_workflow()
        if app_llm:
            return {"status": "success", "message": "Successfully reloaded documents. The new documents are now part of the LLM's context."}
        else:
            return {"status": "success", "message": "No documents found to load. Context reset."}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while reloading documents: {str(e)}"
        )

@app.post("/chat", summary="Send a message and get an assistant response")
async def chat_with_assistant(request: MessageRequest) -> Dict[str, str]:
    """
    Handles a single turn of the conversation.
    Sends a new user message and returns the assistant's reply.
    """
    if not app_llm:
        raise HTTPException(
            status_code=503,
            detail="Error: The LLM model is not ready. No documents were loaded."
        )

    try:
        # LangGraph handles the conversation state using the checkpointer
        user_message = HumanMessage(content=request.message)
        
        # We need to get the current state and append the new message to it.
        # LangGraph's checkpointer handles the state update automatically.
        output = await app_llm.ainvoke({"messages": [user_message]}, config)
        
        # Extract the last message from the assistant
        assistant_response = output["messages"][-1].content
        
        return {"response": assistant_response}

    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing the request: {str(e)}"
        )

@app.get("/chat/history", summary="Get the full conversation history")
async def get_chat_history() -> List[HistoryMessage]:
    """
    Retrieves all messages for the current conversation thread.
    """
    if not app_llm:
        raise HTTPException(
            status_code=503,
            detail="Error: The LLM model is not ready. No documents were loaded."
        )

    try:
        # Use `aget_state` for asynchronous state retrieval
        state = await app_llm.aget_state(config)
        if not state:
            return []
        
        messages = state.values["messages"]
        history = [
            HistoryMessage(content=msg.content, type=msg.type)
            for msg in messages
            if isinstance(msg, BaseMessage)
        ]
        return history
    except Exception as e:
        print(f"Error getting chat history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while retrieving history: {str(e)}"
        )

@app.post("/chat/reset", summary="Reset the current conversation")
async def reset_conversation() -> Dict[str, str]:
    """
    Clears the conversation history for the hardcoded thread ID.
    """
    if not app_llm:
        raise HTTPException(
            status_code=503,
            detail="Error: The LLM model is not ready. No documents were loaded."
        )
    
    try:
        # This is the correct way to clear the state using LangGraph's checkpointer
        await app_llm.checkpointer.put(
            config=config["configurable"],
            checkpoint={
                "v": 1,
                "ts": "2023-01-01T00:00:00.000Z",
                "id": "reset",
                "channel_values": {"messages": []},
            }
        )
        return {"status": "success", "message": "Conversation history has been reset."}
    except Exception as e:
        print(f"Error resetting conversation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while resetting the conversation: {str(e)}"
        )