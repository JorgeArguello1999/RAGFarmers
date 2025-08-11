import streamlit as st
import requests
import json
from typing import Optional, List, Dict, Any

# Configuración de la página
st.set_page_config(
    page_title="Análisis de Licitación y Chat",
    page_icon="📊",
    layout="wide"
)

# URLs de la API
API_BASE_URL = "http://127.0.0.1:8000"
BASE_CHAT_URL = f"{API_BASE_URL}/api/v1/llm"
DASHBOARD_URL = f"{BASE_CHAT_URL}/dashboard"  # Nueva URL para el dashboard
UPLOAD_URL = f"{API_BASE_URL}/api/v1/files/upload-pdfs/"
STATUS_URL = f"{API_BASE_URL}/api/v1/check/status"
CHAT_URL = f"{BASE_CHAT_URL}/chat"
RESET_URL = f"{BASE_CHAT_URL}/chat/reset"
HISTORY_URL = f"{BASE_CHAT_URL}/chat/history"

# Inicializar el estado de la sesión
if "messages" not in st.session_state:
    st.session_state.messages = []
if "files_ready" not in st.session_state:
    st.session_state.files_ready = False
if "dashboard_data" not in st.session_state:
    st.session_state.dashboard_data = None

# --- Funciones de la API ---

def check_files_status():
    """Verifica si los archivos están listos para usar"""
    try:
        response = requests.get(STATUS_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("status", False)
        return False
    except requests.RequestException as e:
        st.error(f"Error al verificar el estado de los archivos: {e}")
        return False

def upload_files(files):
    """Sube archivos PDF al servidor"""
    try:
        files_data = [("files", (file.name, file.getvalue(), "application/pdf")) for file in files]
        response = requests.post(UPLOAD_URL, files=files_data, timeout=30)
        
        if 200 <= response.status_code < 300:
            return True, "Archivos subidos correctamente"
        else:
            return False, f"Error al subir archivos: {response.status_code} - {response.text}"
    except requests.RequestException as e:
        return False, f"Error de conexión: {e}"

def post_chat_message(message: str) -> Optional[str]:
    """Envía un mensaje a la API y devuelve la respuesta del asistente"""
    try:
        response = requests.post(CHAT_URL, json={"message": message}, timeout=30)
        response.raise_for_status()
        return response.json().get("response")
    except requests.RequestException as e:
        st.error(f"Error al enviar el mensaje al chat: {e}")
        return None

def reset_conversation():
    """Limpia el historial de la conversación en el backend"""
    try:
        response = requests.post(RESET_URL, timeout=10)
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        st.error(f"Error al limpiar la conversación: {e}")
        return False

def fetch_dashboard_data():
    """Obtiene los datos del dashboard desde la API"""
    try:
        response = requests.get(DASHBOARD_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Error al obtener los datos del dashboard: {e}")
        return None

# --- Componentes del Dashboard ---

def show_dashboard(data: Dict[str, Any]):
    """Muestra el dashboard basado en los datos del JSON"""
    st.title("📊 Dashboard de Análisis de Licitación")

    st.subheader("Información General del Contrato")
    col1, col2, col3 = st.columns(3)
    
    # Presupuesto
    with col1:
        presupuesto = data.get("analisis_pliego", {}).get("condiciones_economicas", {}).get("presupuesto", {})
        amount = presupuesto.get("amount")
        currency = presupuesto.get("currency_code")
        st.metric(label="Presupuesto Referencial", value=f"{amount:,.2f} {currency}" if amount else "N/A")

    # Plazo de Ejecución
    with col2:
        plazo_data = data.get("analisis_pliego", {}).get("condiciones_legales", {}).get("plazos", [{}])[0]
        plazo_dias = plazo_data.get("normalized", {}).get("duration_days")
        st.metric(label="Plazo de Ejecución", value=f"{plazo_dias} días" if plazo_dias else "N/A")

    # Anticipo
    with col3:
        anticipo_data = data.get("analisis_pliego", {}).get("condiciones_economicas", {}).get("anticipo", {})
        anticipo_pct = anticipo_data.get("percentage")
        st.metric(label="Porcentaje de Anticipo", value=f"{anticipo_pct}%" if anticipo_pct else "N/A")

    st.markdown("---")

    st.subheader("Análisis de Requisitos Técnicos")
    requisitos = data.get("analisis_pliego", {}).get("requisitos_tecnicos", [{}])[0]
    
    with st.expander("Materiales"):
        materiales = requisitos.get("materiales", [])
        if materiales:
            st.markdown(", ".join(materiales))
        else:
            st.info("No se encontraron materiales.")
    
    with st.expander("Procesos"):
        procesos = requisitos.get("procesos", [])
        if procesos:
            st.markdown(", ".join(procesos))
        else:
            st.info("No se encontraron procesos.")

    st.markdown("---")

    st.subheader("Alertas y Contradicciones")
    
    # Contradicciones del pliego vs ley
    st.markdown("#### Pliego vs. Ley")
    contradictorias_ley = data.get("analisis_pliego_vs_ley", {}).get("clausulas_contradictorias", [])
    if contradictorias_ley:
        for contradiccion in contradictorias_ley:
            st.warning(f"⚠️ **Contradicción:** {contradiccion}")
    else:
        st.success("✅ No se encontraron contradicciones significativas entre el pliego y la ley.")

    # Contradicciones del pliego vs contrato
    st.markdown("#### Pliego vs. Contrato")
    contradictorias_contrato = data.get("analisis_pliego_vs_contrato", {}).get("clausulas_contradictorias", [])
    if contradictorias_contrato:
        for contradiccion in contradictorias_contrato:
            st.error(f"❌ **Contradicción:** {contradiccion}")
    else:
        st.success("✅ No se encontraron contradicciones entre el pliego y el contrato.")

    st.markdown("---")

    st.subheader("Cláusulas Faltantes")
    faltantes = data.get("analisis_pliego_vs_ley", {}).get("clausulas_faltantes", [])
    if faltantes:
        st.info("ℹ️ El pliego no incluye las siguientes cláusulas obligatorias de la Ley:")
        st.table({"Cláusula Faltante": faltantes})
    else:
        st.success("✅ No se encontraron cláusulas faltantes.")

# --- Interfaz principal ---
st.title("📚 Análisis de Licitación y Chat")

# Sidebar para subir archivos y estado
with st.sidebar:
    st.header("📄 Subir Archivos PDF")
    
    uploaded_files = st.file_uploader(
        "Selecciona archivos PDF",
        type="pdf",
        accept_multiple_files=True,
        help="Puedes subir múltiples archivos PDF"
    )
    
    if uploaded_files:
        if st.button("Subir Archivos", type="primary"):
            with st.spinner("Subiendo archivos..."):
                success, message = upload_files(uploaded_files)
                if success:
                    st.success(message)
                    st.session_state.files_ready = False
                    st.session_state.dashboard_data = None  # Reiniciar datos del dashboard
                else:
                    st.error(message)
    
    st.header("📊 Estado del Sistema")
    
    if st.button("Verificar Estado"):
        with st.spinner("Verificando estado..."):
            st.session_state.files_ready = check_files_status()
            if st.session_state.files_ready:
                st.success("✅ Archivos procesados y listos")
            else:
                st.warning("⏳ Archivos en procesamiento o no subidos")
    
    if st.session_state.files_ready:
        st.success("✅ Archivos procesados y listos")
    else:
        st.warning("⏳ Archivos en procesamiento o no subidos")
    
    st.info(f"💬 Mensajes en la sesión: {len(st.session_state.messages)}")
    
    if st.button("🗑️ Limpiar Chat", help="Esto reiniciará la conversación en el servidor y en la app."):
        if reset_conversation():
            st.session_state.messages = []
            st.session_state.dashboard_data = None
            st.rerun()

# --- Contenido principal con Tabs ---

tab_dashboard, tab_chat = st.tabs(["📊 Dashboard", "💬 Chat"])

with tab_dashboard:
    st.header("Dashboard de Análisis")
    if st.session_state.files_ready:
        if st.button("Actualizar Dashboard"):
            with st.spinner("Cargando datos del dashboard..."):
                st.session_state.dashboard_data = fetch_dashboard_data()
        
        if st.session_state.dashboard_data:
            show_dashboard(st.session_state.dashboard_data)
        else:
            st.info("Haz clic en 'Actualizar Dashboard' para cargar el análisis del pliego.")
    else:
        st.warning("Espera a que los archivos estén procesados para ver el dashboard.")


with tab_chat:
    st.header("Chat con Documentos")
    # Área del chat
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    chat_disabled = not st.session_state.files_ready

    if chat_disabled:
        st.info("⏳ Espera a que los archivos estén procesados para chatear")

    # Entrada del usuario y lógica del chat
    if prompt := st.chat_input("Escribe tu pregunta aquí...", disabled=chat_disabled):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.spinner("Procesando..."):
            assistant_response = post_chat_message(prompt)

        if assistant_response:
            st.session_state.messages.append({"role": "assistant", "content": assistant_response})
            with st.chat_message("assistant"):
                st.markdown(assistant_response)