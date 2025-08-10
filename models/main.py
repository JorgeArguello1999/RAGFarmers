from dotenv import load_dotenv
load_dotenv()

import os
# api_key = os.getenv("API_KEY")  


# https://python.langchain.com/docs/tutorials/chatbot/
import sys
from pathlib import Path


MAIN_PATH = Path(sys.modules["__main__"].__file__).resolve()

src_dir = os.path.join(MAIN_PATH, "src")
sys.path.append(src_dir)
os.chdir(MAIN_PATH.parent)

from langchain_core.messages import HumanMessage, AIMessage
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.config import ContextoGeneral, PromptExtraccionPliegos
from src.ocr import extract_pdf

ID_CONTRATACION = 'LICO-GADM-S-2024-001-202671'

dir_pliegos_md = os.path.join(f'data/raw/{ID_CONTRATACION} - Pliegos.md')
dir_pliegos_pdf = os.path.join(f'data/raw/{ID_CONTRATACION} - Pliegos.pdf')
dir_pliegos_llm = os.path.join(f'data/raw/{ID_CONTRATACION} - Pliegos_llm.txt')

#--------------------------------------------------------------------#
# ocr
if os.path.exists(dir_pliegos_md):
    if input("¿Desea extraer OCR nuevamente?").lower()=='si':
        os.remove(dir_pliegos_md)

if not os.path.exists(dir_pliegos_md):
    print("-"*20)
    print("OCR Transforming...")
    md_pliegos = extract_pdf(dir=os.path.join(dir_pliegos_pdf))
    with open(dir_pliegos_md, "w", encoding="utf-8") as f:
        f.write(md_pliegos)

if os.path.exists(dir_pliegos_md):
    print("-"*20)
    print("OCR loaded from md!")
    with open(dir_pliegos_md, "r", encoding="utf-8") as f:
        md_pliegos = f.read()
    

#--------------------------------------------------------------------#
# llm
workflow = StateGraph(state_schema=MessagesState)
model = init_chat_model("gpt-4o-mini", model_provider="openai", temperature = 0)
prompt_template = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            ContextoGeneral,
        ),
        MessagesPlaceholder(variable_name="messages"),
    ]
)
prompt_template = ChatPromptTemplate.from_messages(
    [
        ("system", ContextoGeneral),
        ("system", "Documento en Markdown:\n{markdown}"),
        MessagesPlaceholder(variable_name="messages"),
    ]
).partial(markdown=md_pliegos)

def call_model(state: MessagesState):
    prompt = prompt_template.invoke(state)
    response = model.invoke(prompt)
    return {"messages": response}
workflow.add_edge(START, "model")
workflow.add_node("model", call_model)
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
config = {"configurable": {"thread_id": "abc123"}}



input_messages = [HumanMessage(PromptExtraccionPliegos(md_pliegos))]
print('LLM procesando solicitud:')
output = app.invoke({"messages": input_messages}, config)
print(output["messages"][-1].content)
with open(dir_pliegos_llm, 'w') as f:
    f.write(output["messages"][-1].content)

continuar_conversacion = input('¿Desea continuar con la conversación usando LLM?')
#while continuar_conversacion.lower()=='si':
while True:
    input_text = input('¿Qué deseas saber sobre la licitación?')
    input_messages.append(HumanMessage(content="vuelve a leer el documento, responde: "+ input_text))
    output_i = app.invoke({"messages": input_messages}, config)
    print(output_i["messages"][-1].content)
    #continuar_conversacion = input('¿Desea continuar con la conversación usando LLM?')