from dotenv import load_dotenv
load_dotenv()

import os
import sys
from pathlib import Path
import asyncio
import redis.asyncio as redis

from langchain_core.messages import HumanMessage
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.config import ContextoGeneral, PromptExtraccionPliegos

# -------------------
# Configuración Redis
# -------------------
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "devpass123")

# Redis client (async mode)
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=False 
)

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

async def main():
    markdown_unido, nombres = await get_all_markdown_docs()
    if not markdown_unido:
        print("No hay documentos Markdown en Redis.")
        return
    
    print(f"Documentos cargados desde Redis: {', '.join(nombres)}")
    print(f"Total de documentos: {len(nombres)}")
    
    # Prompt con todos los documentos juntos
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
    app = workflow.compile(checkpointer=memory)
    config = {"configurable": {"thread_id": "conv_unica"}}

    # Primera pregunta al LLM
    input_messages = [HumanMessage(PromptExtraccionPliegos(markdown_unido))]
    print("\nLLM procesando solicitud inicial...")
    output = app.invoke({"messages": input_messages}, config)
    print(output["messages"][-1].content)

    # Conversación continua
    while True:
        pregunta = input('\n¿Qué deseas saber sobre los documentos? (o "salir" para terminar): ')
        if pregunta.lower() == "salir":
            break
        input_messages.append(HumanMessage(content="vuelve a leer todos los documentos, responde: " + pregunta))
        output_i = app.invoke({"messages": input_messages}, config)
        print(output_i["messages"][-1].content)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nEjecución interrumpida por el usuario.")
