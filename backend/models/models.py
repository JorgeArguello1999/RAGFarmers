import os
api_key= os.environ["OPENAI_API_KEY"] 

# https://python.langchain.com/docs/tutorials/chatbot/
import sys
from pathlib import Path

import json, re, pathlib

MAIN_PATH = Path(sys.modules["__main__"].__file__).resolve()

src_dir = os.path.join(MAIN_PATH, "src")
sys.path.append(src_dir)
os.chdir(MAIN_PATH.parent)

from langchain_core.messages import HumanMessage, AIMessage
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI  # <-- ChatGPT via LangChain
# from langchain.chains.combine_documents import create_stuff_documents_chain
# from langchain.chains import create_retrieval_chain
from langchain_core.output_parsers import StrOutputParser
import tiktoken, numpy as np
import pickle
from sentence_transformers import SentenceTransformer
from tenacity import retry, wait_exponential, stop_after_attempt

from src.config import (ContextoGeneralPliegos, PromptExtraccionPliegos,
                        ContextoGeneralPliegosvsLey, PromptExtraccionPliegosvsLey,
                        ContextoGeneralPliegosvsContrato, PromptExtraccionPliegosvsContrato,
                        PromptAnalisisDocsPropuestaSystem, PromptAnalisisDocsPropuestaUser,
                        ContextoGeneralOfertaPrincipalvsOtros, PromptExtraccionOfertaPrincipalvsOtros)
from src.ocr import extract_pdf

ID_CONTRATACION = 'LICO-GADM-S-2024-001-202671'

#dirs
## pliegos
dir_pliegos_md = os.path.join(f'data/raw/{ID_CONTRATACION} - Pliegos.md')
dir_pliegos_pdf = os.path.join(f'data/raw/{ID_CONTRATACION} - Pliegos.pdf')
dir_pliegos_llm = os.path.join(f'data/outputs/{ID_CONTRATACION} - Pliegos_llm.txt')
## ley contratación
dir_ley_md = os.path.join(f'data/raw/losncp_actualizada1702.md')
dir_ley_pdf = os.path.join(f'data/raw/losncp_actualizada1702.pdf')
## contrato
dir_contrato_md = os.path.join(f'data/raw/{ID_CONTRATACION} - Contrato.md')
dir_contrato_pdf = os.path.join(f'data/raw/{ID_CONTRATACION} - Contrato.pdf')

## otros
dir_pliegos_ley_llm = os.path.join(f'data/outputs/{ID_CONTRATACION} - PliegosvsLey_llm.txt')
dir_pliegos_contrato_llm = os.path.join(f'data/outputs/{ID_CONTRATACION} - PliegosvsContrato_llm.txt')

dir_salida = os.path.join(f'data/outputs/{ID_CONTRATACION} - salida.json')

dir_comparacion_ofertas = os.path.join(f'data/outputs/{ID_CONTRATACION} - comparacion_ofertas.txt')

#--------------------------------------------------------------------#
# ocr
## nuevo ocr?
if os.path.exists(dir_pliegos_md):
    if input("¿Desea extraer OCR pliegos nuevamente?").lower()=='si':
        os.remove(dir_pliegos_md)

if os.path.exists(dir_contrato_md):
    if input("¿Desea extraer OCR contrato nuevamente?").lower()=='si':
        os.remove(dir_contrato_md)

if os.path.exists(dir_ley_md):
    if input("¿Desea extraer OCR Ley Contratación Pública nuevamente?").lower()=='si':
        os.remove(dir_ley_md)

## nuevo ocr?
def ocr_to_md(dir_pliegos_md, dir_pliegos_pdf):
    if not os.path.exists(dir_pliegos_md):
        print("-"*20)
        print(f"OCR Transforming {dir_pliegos_md.split('/')[-1]}...")
        md_pliegos = extract_pdf(dir=os.path.join(dir_pliegos_pdf))
        with open(dir_pliegos_md, "w", encoding="utf-8") as f:
            f.write(md_pliegos)

    if os.path.exists(dir_pliegos_md):
        print("-"*20)
        print(f"OCR loaded from md {dir_pliegos_md.split('/')[-1]}!")
        with open(dir_pliegos_md, "r", encoding="utf-8") as f:
            md_pliegos = f.read()
    return md_pliegos

def cargar_md(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

md_pliegos = ocr_to_md(dir_pliegos_md, dir_pliegos_pdf)
md_ley = ocr_to_md(dir_ley_md, dir_ley_pdf)
md_contrato = ocr_to_md(dir_contrato_md, dir_contrato_pdf)

md_oferta_0 = cargar_md(os.path.join(f'data/outputs/{ID_CONTRATACION} - consolidado.md'))
md_oferta_1 = cargar_md(os.path.join(f'data/outputs/LICO-GADM-M-2025-002-345891 - consolidado.md'))
md_oferta_2 = cargar_md(os.path.join(f'data/outputs/LICO-GADM-P-2025-003-567123 - consolidado.md'))
md_oferta_3 = cargar_md(os.path.join(f'data/outputs/LICO-GADM-O-2025-004-789456 - consolidado.md'))

#--------------------------------------------------------------------#
# llms
#--------------------------------------------------------------------#

## análisis pliegos
def llm_pliegos(model_name = 'gpt-4o-mini', model_provider = 'openai'):
    workflow = StateGraph(state_schema=MessagesState)
    model = init_chat_model(model_name, model_provider= model_provider, temperature = 0)
    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", ContextoGeneralPliegos),
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
    config = {"configurable": {"thread_id": "a1"}}



    #input_messages = [HumanMessage(PromptExtraccionPliegos(md_pliegos))]
    input_messages = [HumanMessage(PromptExtraccionPliegos())]
    print('LLM procesando solicitud análisis pliegos:')
    output = app.invoke({"messages": input_messages}, config)
    print(output["messages"][-1].content)
    with open(dir_pliegos_llm, 'w') as f:
        f.write(output["messages"][-1].content)

    continuar_conversacion = input('¿Desea continuar con la conversación usando LLM?')
    while continuar_conversacion.lower()=='si':
        input_text = input('¿Qué deseas saber sobre la licitación?')
        input_messages.append(HumanMessage(content="vuelve a leer el documento, responde: "+ input_text))
        output_i = app.invoke({"messages": input_messages}, config)
        print(output_i["messages"][-1].content)
        continuar_conversacion = input('¿Desea continuar con la conversación usando LLM?')


def llm_pliegos_vs_ley(model_name = 'gpt-4o-mini', model_provider = 'openai'):
    workflow = StateGraph(state_schema=MessagesState)
    model = init_chat_model(model_name, model_provider= model_provider, temperature = 0)
    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", ContextoGeneralPliegosvsLey),
            ("system", "Documento en Markdown 1:\n{markdown_1}"),
            ("system", "Documento en Markdown 2:\n{markdown_2}"),
            MessagesPlaceholder(variable_name="messages"),
        ]
    ).partial(markdown_1=md_pliegos, markdown_2=md_ley)

    def call_model(state: MessagesState):
        prompt = prompt_template.invoke(state)
        response = model.invoke(prompt)
        return {"messages": response}
    workflow.add_edge(START, "model")
    workflow.add_node("model", call_model)
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    config = {"configurable": {"thread_id": "a2"}}



    input_messages = [HumanMessage(PromptExtraccionPliegosvsLey)]
    print('LLM procesando solicitud Pliegos vs. Ley:')
    output = app.invoke({"messages": input_messages}, config)
    print(output["messages"][-1].content)
    with open(dir_pliegos_ley_llm , 'w') as f:
        f.write(output["messages"][-1].content)

    continuar_conversacion = input('¿Desea continuar con la conversación usando LLM?')
    while continuar_conversacion.lower()=='si':
        input_text = input('¿Qué deseas saber sobre la comparación?')
        input_messages.append(HumanMessage(content=input_text))
        output_i = app.invoke({"messages": input_messages}, config)
        print(output_i["messages"][-1].content)
        continuar_conversacion = input('¿Desea continuar con la conversación usando LLM?')

def llm_pliegos_vs_contrato(model_name = 'gpt-4o-mini', model_provider = 'openai'):
    workflow = StateGraph(state_schema=MessagesState)
    model = init_chat_model(model_name, model_provider= model_provider, temperature = 0)

    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", ContextoGeneralPliegosvsContrato),
            ("system", "Documento en Markdown 1:\n{markdown_1}"),
            ("system", "Documento en Markdown 2:\n{markdown_2}"),
            MessagesPlaceholder(variable_name="messages"),
        ]
    ).partial(markdown_1=md_pliegos, markdown_2=md_contrato)

    def call_model(state: MessagesState):
        prompt = prompt_template.invoke(state)
        response = model.invoke(prompt)
        return {"messages": response}
    workflow.add_edge(START, "model")
    workflow.add_node("model", call_model)
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    config = {"configurable": {"thread_id": "a2"}}



    input_messages = [HumanMessage(PromptExtraccionPliegosvsContrato)]
    print('LLM procesando solicitud Pliegos vs. Contrato:')
    output = app.invoke({"messages": input_messages}, config)
    print(output["messages"][-1].content)
    with open(dir_pliegos_contrato_llm, 'w') as f:
        f.write(output["messages"][-1].content)

    continuar_conversacion = input('¿Desea continuar con la conversación usando LLM?')
    while continuar_conversacion.lower()=='si':
        input_text = input('¿Qué deseas saber sobre la comparación?')
        input_messages.append(HumanMessage(content=input_text))
        output_i = app.invoke({"messages": input_messages}, config)
        print(output_i["messages"][-1].content)
        continuar_conversacion = input('¿Desea continuar con la conversación usando LLM?')



def estimate_tokens(text: str, enc_name: str = "o200k_base") -> int:
    """Estima tokens para modelos 4o/4.1 (usa 'cl100k_base' si prefieres)."""
    enc = tiktoken.get_encoding(enc_name)
    return len(enc.encode(text))

def select_context(topic: str, doc_text: str,
                   max_ctx_tokens: int = 6000,
                   chunk_size: int = 1200,
                   overlap: int = 200,
                   emb_model: str = "sentence-transformers/all-MiniLM-L6-v2") -> str:
    """Elige los chunks más similares al topic bajo un presupuesto de tokens."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    chunks = splitter.split_text(doc_text) or [doc_text]

    emb = SentenceTransformer(emb_model)
    q = emb.encode([topic], normalize_embeddings=True)
    M = emb.encode(chunks, normalize_embeddings=True)
    scores = (M @ q.T).ravel()
    order = np.argsort(-scores)

    selected, total = [], 0
    for i in order:
        c = chunks[i]
        t = estimate_tokens(c)
        # si el chunk solo ya supera el budget, intenta meterlo igual si no hay nada aún
        if total == 0 and t > max_ctx_tokens:
            selected = [c[: int(len(c) * (max_ctx_tokens / t) * 0.95)]]
            break
        if total + t <= max_ctx_tokens:
            selected.append(c)
            total += t
        if total >= max_ctx_tokens * 0.95:
            break

    if not selected:
        selected = [chunks[order[0]]]
    return "\n\n".join(selected)

def parse_json_robusto(texto: str):
    """Extrae el primer bloque {...} por si el LLM añadió texto extra."""
    if not texto or not texto.strip():
        raise ValueError("Respuesta vacía del modelo.")
    m = re.search(r"\{.*\}", texto, flags=re.S)
    if not m:
        raise ValueError("No se encontró JSON en la respuesta.")
    return json.loads(m.group(0))

@retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(5))
def _invoke_chain(chain, payload):
    return chain.invoke(payload)

def evaluar_tema_documento(topic: str,
                           document_text: str,
                           max_ctx_tokens: int = 60_000,
                           max_output_tokens: int = 1_000):
    prompt = ChatPromptTemplate.from_messages([
        ("system", PromptAnalisisDocsPropuestaSystem),
        ("user", PromptAnalisisDocsPropuestaUser)
    ])

    context = select_context(topic, document_text, max_ctx_tokens=max_ctx_tokens)

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=max_output_tokens,
        model_kwargs={"response_format": {"type": "json_object"}}
    )  # o "chatgpt-o4-nano"
    chain = prompt | llm | StrOutputParser()

    raw = _invoke_chain(chain, {"topic": topic, "document_text": context})
    try:
        return json.loads(raw)
    except Exception:
        return parse_json_robusto(raw)
    
def listar_archivos(carpeta, recursivo= False, patron= "*", incluir_ocultos= True, sin_extension= False):
    """
    Devuelve una lista de rutas (str) de todos los archivos en `carpeta`.
    - recursivo: busca también en subcarpetas.
    - patron: filtro tipo glob (p.ej. "*.csv", "*.png").
    - incluir_ocultos: incluye archivos que empiezan con '.'.
    """
    p = Path(carpeta)
    it = p.rglob(patron) if recursivo else p.glob(patron)
    archivos = [
        (x.stem if sin_extension else x.name)
        for x in it
        if x.is_file() and (incluir_ocultos or not x.name.startswith("."))
    ]
    return archivos
    
def consolidar_oferta(dir_oferta, id_contratacion):
    
    list_files = listar_archivos(dir_oferta, incluir_ocultos= False, sin_extension= False)
    list_files_sin_extension = list(set(Path(file).stem for file in list_files))
    oferta = {}
    for file in list_files_sin_extension:
        with open(dir_oferta / f"{file}.md", "r", encoding="utf-8") as f:
            markdown = f.read()
            oferta[file] = markdown

    evaluacion = {}
    for ind, (name_doc, markdown) in enumerate(oferta.items(), 1):
        print(f'Analizando {ind} - {name_doc}')
        consulta = evaluar_tema_documento(
            'Condiciones legales (garantías, multas, plazos), Requisitos técnicos (materiales, procesos, tiempos), Condiciones económicas (presupuestos, formas de pago)',
            markdown,
            max_ctx_tokens=60_000,              # ajusta según tu límite
            max_output_tokens=1_000
        )
        if consulta['similarity_score'] >= 0.6:
            evaluacion[name_doc] = consulta

    consulta_final = ''
    for name_doc in evaluacion.keys():
        consulta = oferta[name_doc]
        consulta_final += f"## {name_doc}\n\n{consulta}\n\n"

    folder_preprocesed = Path("data/processed")
    folder_preprocesed.mkdir(parents=True, exist_ok=True)
    with open(f"data/processed/{id_contratacion} - evaluacion_markdowns.pkl", "wb") as f:
        pickle.dump(evaluacion, f, protocol=pickle.HIGHEST_PROTOCOL)

    folder_outputs = Path("data/outputs")
    folder_outputs.mkdir(parents=True, exist_ok=True)
    with open(f"data/outputs/{id_contratacion} - consolidado.md", "w", encoding="utf-8") as f:
        f.write(consulta_final)

def consolidar_todas_ofertas():
    id_ofertas = [
        ID_CONTRATACION, 
        "LICO-GADM-M-2025-002-345891",
        "LICO-GADM-P-2025-003-567123",
        "LICO-GADM-O-2025-004-789456"
        ]
    for id_con in id_ofertas:
        if id_con == ID_CONTRATACION:
            dir_con = Path(__file__).parent / "data" / "raw" / f"{ID_CONTRATACION} - oferta ganadora"
        else:
            dir_con = Path(__file__).parent / "data" / "generated" / f"{id_con} - oferta generada"

        if not Path(f"data/outputs/{id_con} - consolidado.md").exists():
            print(f'consolidando oferta: {id_con}')
            consolidar_oferta(dir_con, id_con)

def _safe_invoke_model(model, prompt_messages):
    return model.invoke(prompt_messages)

def oferta_principal_vs_otras(
        model_name='gpt-4o-mini',
        model_provider='openai',
        *,
        per_doc_ctx_tokens=1500,   # presupuesto por documento
        chunk_size=1200,
        overlap=200,
        max_output_tokens=700):
    
    model = init_chat_model(model_name,
                            model_provider= model_provider,
                            temperature = 0,
                            max_tokens=max_output_tokens)

    documentos = [md_oferta_0, md_oferta_1, md_oferta_2, md_oferta_3]

    def build_prompt_for_query(query_text: str):
        # Para cada documento, selecciona contexto bajo presupuesto
        reduced_docs = [
            select_context(
                topic=query_text,
                doc_text=doc,
                max_ctx_tokens=per_doc_ctx_tokens,
                chunk_size=chunk_size,
                overlap=overlap
            )
            for doc in documentos
        ]

        # Crea el template con placeholders y “partial” con los textos reducidos
        prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", ContextoGeneralOfertaPrincipalvsOtros),
                ("system", "Documento en Markdown 0:\n{markdown_0}"),
                ("system", "Documento en Markdown 1:\n{markdown_1}"),
                ("system", "Documento en Markdown 2:\n{markdown_2}"),
                ("system", "Documento en Markdown 3:\n{markdown_3}"),
                MessagesPlaceholder(variable_name="messages"),
            ]
        ).partial(
            markdown_0=reduced_docs[0],
            markdown_1=reduced_docs[1],
            markdown_2=reduced_docs[2],
            markdown_3=reduced_docs[3],
        )
        return prompt_template

    def call_model(state: MessagesState):
        msgs = state["messages"]
        last_human = next((m for m in reversed(msgs) if isinstance(m, HumanMessage)), None)
        query_text = last_human.content if last_human else PromptExtraccionOfertaPrincipalvsOtros
        prompt_template = build_prompt_for_query(query_text)
        prompt_messages = prompt_template.invoke(state)

        response = _safe_invoke_model(model, prompt_messages)
        return {"messages": response}
    
    workflow = StateGraph(state_schema=MessagesState)
    workflow.add_node("model", call_model)
    workflow.add_edge(START, "model")
    
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    config = {"configurable": {"thread_id": "a2"}}


    input_messages = [HumanMessage(PromptExtraccionOfertaPrincipalvsOtros)]
    print('LLM procesando solicitud Oferta Principal vs. Otros:')
    output = app.invoke({"messages": input_messages}, config)
    print(output["messages"][-1].content)
    with open(dir_comparacion_ofertas, 'w') as f:
        f.write(output["messages"][-1].content)

    continuar_conversacion = input('¿Desea continuar con la conversación usando LLM?')
    while continuar_conversacion.lower()=='si':
        input_text = input('¿Qué deseas saber sobre la comparación?')
        input_messages.append(HumanMessage(content=input_text))
        output_i = app.invoke({"messages": input_messages}, config)
        print(output_i["messages"][-1].content)
        continuar_conversacion = input('¿Desea continuar con la conversación usando LLM?')


llm_pliegos()
llm_pliegos_vs_ley()
llm_pliegos_vs_contrato()
consolidar_todas_ofertas()
oferta_principal_vs_otras()


def _show_error_context(s: str, err: json.JSONDecodeError) -> None:
    lines = s.splitlines()
    start = max(0, err.lineno - 3)
    end = min(len(lines), err.lineno + 2)
    print(f"JSON error: {err.msg} at line {err.lineno}, col {err.colno}")
    for i in range(start, end):
        marker = "  <-- here" if (i + 1) == err.lineno else ""
        print(f"{i+1:>6}: {lines[i]}{marker}")

def _repair_json_like(s: str) -> str:
    # strip BOM
    s = s.lstrip("\ufeff")
    # remove // and /* */ comments
    s = re.sub(r'//.*?(?=\n|$)', '', s)
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    # Python → JSON literals
    s = re.sub(r'\bNone\b', 'null', s)
    s = re.sub(r'\bTrue\b', 'true', s)
    s = re.sub(r'\bFalse\b', 'false', s)
    # quote unquoted keys: { key: ... } or , key: ...
    s = re.sub(r'(?m)(^|[{,]\s*)([A-Za-z_][\w\-]*)(\s*):', r'\1"\2"\3:', s)
    # convert 'single-quoted strings' → "double-quoted strings"
    def _s2d(m):
        inner = m.group(1).replace('\\', '\\\\').replace('"', '\\"')
        return f'"{inner}"'
    s = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", _s2d, s)
    # remove trailing commas before } or ]
    s = re.sub(r',\s*(?=[}\]])', '', s)
    return s

def safe_json_load(obj):
    """
    Accepts a dict/list (returns as-is), a JSON string, or a file path.
    Tries strict JSON first, then json5 (if installed), then auto-repair.
    """
    if isinstance(obj, (dict, list)):
        return obj

    if isinstance(obj, bytes):
        text = obj.decode('utf-8', 'replace')
    elif isinstance(obj, str):
        p = pathlib.Path(obj)
        text = p.read_text(encoding='utf-8') if p.exists() else obj
    else:
        raise TypeError("Unsupported type for JSON input")

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        _show_error_context(text, e)
        # Optional: handle comments, trailing commas, single quotes, etc. via json5 if available
        try:
            import json5  # pip install json5
            return json5.loads(text)
        except Exception:
            repaired = _repair_json_like(text)
            return json.loads(repaired)
 
 

with open(dir_pliegos_llm, 'r', encoding='utf8') as file:
    f1  = file.read()
with open(dir_pliegos_ley_llm, 'r', encoding='utf8') as file:
    f2  = file.read()
with open(dir_pliegos_contrato_llm, 'r', encoding='utf8') as file:
    f3  = file.read()
with open(dir_comparacion_ofertas, 'r', encoding='utf8') as file:
    f4  = file.read()


f1 = safe_json_load(dir_pliegos_llm)
f2 = safe_json_load(dir_pliegos_ley_llm)
f3 = safe_json_load(dir_pliegos_contrato_llm)
f4 = safe_json_load(dir_comparacion_ofertas)

salida_json = {
    "id": ID_CONTRATACION,
    "analisis_pliego" : f1,
    "analisis_pliego_vs_ley" : f2,
    "analisis_pliego_vs_contrato" : f3,
    "analisis_oferta_principal_vs_otros" : f4,
}

with open(dir_salida, 'w', encoding='utf8') as json_file:
    json.dump(salida_json, json_file, ensure_ascii=False)