# app/llm_service.py

import os
import sys
import asyncio
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, BaseMessage
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Import from other modules
from database.redis import redis_client
from models.config import ContextoGeneral

# Global variables for the app state
app_llm = None
markdown_unido_global = None
memory = MemorySaver()
CONVERSATION_THREAD_ID = "conv_unica"
config = {"configurable": {"thread_id": CONVERSATION_THREAD_ID}}
model = init_chat_model("gpt-4o-mini", model_provider="openai", temperature=0)

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

async def reload_documents_context():
    """Reloads documents and updates the LLM context."""
    await initialize_llm_workflow()
    if not app_llm:
        raise Exception("No documents found to load. Context reset.")
    
async def chat_with_assistant_service(message: str) -> str:
    """Handles a single chat turn."""
    if not app_llm:
        raise Exception("The LLM model is not ready. No documents were loaded.")
    
    user_message = HumanMessage(content=message)
    output = await app_llm.ainvoke({"messages": [user_message]}, config)
    return output["messages"][-1].content

async def get_chat_history_service() -> List[BaseMessage]:
    """Retrieves the full conversation history."""
    if not app_llm:
        raise Exception("The LLM model is not ready. No documents were loaded.")
    
    state = await app_llm.aget_state(config)
    return state.values.get("messages", []) if state else []

async def reset_conversation_service():
    """Clears the conversation history."""
    if not app_llm:
        raise Exception("The LLM model is not ready. No documents were loaded.")
    
    await app_llm.checkpointer.put(
        config=config["configurable"],
        checkpoint={
            "v": 1,
            "ts": "2023-01-01T00:00:00.000Z",
            "id": "reset",
            "channel_values": {"messages": []},
        }
    )