from dotenv import load_dotenv
load_dotenv()

import os
import sys
from pathlib import Path
import asyncio
import redis.asyncio as redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from langchain_core.messages import HumanMessage
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.config import ContextoGeneral, PromptExtraccionPliegos
from src.redis_db import redis_client

# -------------------
# Paths
# -------------------
MAIN_PATH = Path(sys.modules["__main__"].__file__).resolve()
src_dir = os.path.join(MAIN_PATH, "src")
sys.path.append(src_dir)
os.chdir(MAIN_PATH.parent)

# -------------------
# LLM y flujo
# -------------------
workflow = StateGraph(state_schema=MessagesState)
model = init_chat_model("gpt-4o-mini", model_provider="openai", temperature=0)

app = FastAPI()

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

# Inicializar el modelo y flujo una vez
@app.on_event("startup")
async def startup_event():
    global app_llm, config, markdown_unido_global

    markdown_unido, nombres = await get_all_markdown_docs()
    if not markdown_unido:
        print("No hay documentos Markdown en Redis.")
        app_llm = None
        return
    
    print(f"Documentos cargados desde Redis: {', '.join(nombres)}")
    print(f"Total de documentos: {len(nombres)}")
    markdown_unido_global = markdown_unido

    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", ContextoGeneral),
            ("system", "Documentos en Markdown:\n{markdown}"),
            MessagesPlaceholder(variable_name="messages"),
        ]
    ).partial(markdown=markdown_unido)

    def call_model(state: MessagesState):
        prompt = prompt_template.invoke(state)
        response = model.invoke(prompt)
        return {"messages": response}

    workflow.add_edge(START, "model")
    workflow.add_node("model", call_model)
    memory = MemorySaver()
    app_llm = workflow.compile(checkpointer=memory)
    config = {"configurable": {"thread_id": "conv_unica"}}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    if not app_llm:
        await websocket.send_text("Error: no hay documentos cargados.")
        await websocket.close()
        return

    input_messages = []

    try:
        while True:
            pregunta = await websocket.receive_text()

            if pregunta.lower() == "salir":
                await websocket.send_text("Conexión cerrada.")
                await websocket.close()
                break

            if not input_messages:
                # Primer mensaje con el prompt inicial
                input_messages.append(HumanMessage(PromptExtraccionPliegos(markdown_unido_global)))
                output = app_llm.invoke({"messages": input_messages}, config)
                await websocket.send_text(output["messages"][-1].content)
            else:
                # Mensajes subsecuentes
                input_messages.append(HumanMessage(content="vuelve a leer todos los documentos, responde: " + pregunta))
                output_i = app_llm.invoke({"messages": input_messages}, config)
                await websocket.send_text(output_i["messages"][-1].content)

    except WebSocketDisconnect:
        print("Cliente desconectado.")
