import streamlit as st
import requests
import json
from typing import Optional, List, Dict, Any

# Configuración de la página
st.set_page_config(
    page_title="Chat con PDFs",
    page_icon="📚",
    layout="wide"
)

# URLs de la API
API_BASE_URL = "http://127.0.0.1:8000"
BASE_CHAT_URL = "http://127.0.0.1:8001"
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

# --- Interfaz principal ---

st.title("📚 Chat con Documentos PDF")

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
            st.rerun()

# Área principal del chat
st.header("💬 Chat")

# Mostrar mensajes históricos del chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

chat_disabled = not st.session_state.files_ready

if chat_disabled:
    st.info("⏳ Espera a que los archivos estén procesados para chatear")

# Entrada del usuario y lógica del chat
if prompt := st.chat_input("Escribe tu pregunta aquí...", disabled=chat_disabled):
    # Añadir el mensaje del usuario a la sesión
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Mostrar el mensaje del usuario
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Enviar el mensaje a la API y obtener la respuesta
    with st.spinner("Procesando..."):
        assistant_response = post_chat_message(prompt)

    # Añadir y mostrar la respuesta del asistente
    if assistant_response:
        st.session_state.messages.append({"role": "assistant", "content": assistant_response})
        with st.chat_message("assistant"):
            st.markdown(assistant_response)

