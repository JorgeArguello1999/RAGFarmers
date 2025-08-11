import streamlit as st
import requests
import websocket
import json
import threading
import time
from typing import Optional
import queue

# Configuración de la página
st.set_page_config(
    page_title="Chat con PDFs",
    page_icon="📚",
    layout="wide"
)

# URLs de la API
API_BASE_URL = "http://127.0.0.1:8000/api/v1"
UPLOAD_URL = f"{API_BASE_URL}/files/upload-pdfs/"
STATUS_URL = f"{API_BASE_URL}/check/status"
WS_URL = "ws://127.0.0.1:8001/ws"

# Inicializar el estado de la sesión
if "messages" not in st.session_state:
    st.session_state.messages = []
if "ws_connected" not in st.session_state:
    st.session_state.ws_connected = False
if "files_ready" not in st.session_state:
    st.session_state.files_ready = False
if "ws" not in st.session_state:
    st.session_state.ws = None
if "message_queue" not in st.session_state:
    st.session_state.message_queue = queue.Queue()

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
        files_data = []
        for file in files:
            files_data.append(("files", (file.name, file.getvalue(), "application/pdf")))
        
        response = requests.post(UPLOAD_URL, files=files_data, timeout=30)
        
        if response.status_code == 200 or response.status_code == 201:
            return True, "Archivos subidos correctamente"
        else:
            return False, f"Error al subir archivos: {response.status_code}"
    except requests.RequestException as e:
        return False, f"Error de conexión: {e}"

class WebSocketHandler:
    def __init__(self):
        self.ws = None
        self.connected = False
        
    def on_message(self, ws, message):
        """Maneja los mensajes recibidos del WebSocket"""
        try:
            data = json.loads(message)
            st.session_state.message_queue.put(data)
        except json.JSONDecodeError:
            st.session_state.message_queue.put({"type": "error", "content": "Error al decodificar mensaje"})
    
    def on_error(self, ws, error):
        """Maneja errores del WebSocket"""
        st.session_state.message_queue.put({"type": "error", "content": f"Error de WebSocket: {error}"})
        self.connected = False
    
    def on_close(self, ws, close_status_code, close_msg):
        """Maneja el cierre del WebSocket"""
        self.connected = False
        st.session_state.ws_connected = False
    
    def on_open(self, ws):
        """Maneja la apertura del WebSocket"""
        self.connected = True
        st.session_state.ws_connected = True
    
    def connect(self):
        """Conecta al WebSocket"""
        try:
            self.ws = websocket.WebSocketApp(
                WS_URL,
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close
            )
            
            # Ejecutar en un hilo separado
            def run_ws():
                self.ws.run_forever()
            
            ws_thread = threading.Thread(target=run_ws, daemon=True)
            ws_thread.start()
            
        except Exception as e:
            st.error(f"Error al conectar WebSocket: {e}")
    
    def send_message(self, message):
        """Envía un mensaje a través del WebSocket"""
        if self.ws and self.connected:
            try:
                self.ws.send(json.dumps({"message": message}))
                return True
            except Exception as e:
                st.error(f"Error al enviar mensaje: {e}")
                return False
        return False

def process_websocket_messages():
    """Procesa los mensajes recibidos del WebSocket"""
    while not st.session_state.message_queue.empty():
        try:
            message = st.session_state.message_queue.get_nowait()
            if message.get("type") == "error":
                st.error(message.get("content", "Error desconocido"))
            else:
                # Agregar mensaje del asistente
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": message.get("content", message.get("message", "Respuesta recibida"))
                })
        except queue.Empty:
            break

# Interfaz principal
st.title("📚 Chat con Documentos PDF")

# Sidebar para subir archivos
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
                    st.session_state.files_ready = False  # Reset status
                else:
                    st.error(message)
    
    # Verificar estado de los archivos
    st.header("📊 Estado del Sistema")
    
    if st.button("Verificar Estado"):
        with st.spinner("Verificando estado..."):
            st.session_state.files_ready = check_files_status()
    
    # Mostrar estado
    if st.session_state.files_ready:
        st.success("✅ Archivos procesados y listos")
    else:
        st.warning("⏳ Archivos en procesamiento o no subidos")
    
    # Conexión WebSocket
    st.header("🔌 Conexión")
    
    if not st.session_state.ws_connected:
        if st.button("Conectar Chat"):
            ws_handler = WebSocketHandler()
            ws_handler.connect()
            st.session_state.ws_handler = ws_handler
            time.sleep(1)  # Esperar un poco para la conexión
    else:
        st.success("✅ Chat conectado")
        if st.button("Desconectar"):
            if hasattr(st.session_state, 'ws_handler') and st.session_state.ws_handler.ws:
                st.session_state.ws_handler.ws.close()
            st.session_state.ws_connected = False

# Área principal del chat
col1, col2 = st.columns([3, 1])

with col1:
    st.header("💬 Chat")
    
    # Mostrar mensajes del chat
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Procesar mensajes del WebSocket
    process_websocket_messages()
    
    # Input del chat
    chat_disabled = not (st.session_state.files_ready and st.session_state.ws_connected)
    
    if chat_disabled:
        if not st.session_state.files_ready:
            st.info("⏳ Espera a que los archivos estén procesados para chatear")
        elif not st.session_state.ws_connected:
            st.info("🔌 Conecta el chat para comenzar a conversar")
    
    if prompt := st.chat_input("Escribe tu pregunta aquí...", disabled=chat_disabled):
        # Agregar mensaje del usuario
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Mostrar mensaje del usuario
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Enviar mensaje por WebSocket
        if hasattr(st.session_state, 'ws_handler'):
            with st.chat_message("assistant"):
                with st.spinner("Procesando..."):
                    success = st.session_state.ws_handler.send_message(prompt)
                    if not success:
                        st.error("Error al enviar mensaje. Verifica la conexión.")

with col2:
    st.header("ℹ️ Estado")
    
    # Estado de conexión
    if st.session_state.ws_connected:
        st.success("🟢 Chat conectado")
    else:
        st.error("🔴 Chat desconectado")
    
    # Estado de archivos
    if st.session_state.files_ready:
        st.success("🟢 Archivos listos")
    else:
        st.warning("🟡 Archivos no listos")
    
    # Información adicional
    st.info(f"💬 Mensajes: {len(st.session_state.messages)}")
    
    # Botón para limpiar chat
    if st.button("🗑️ Limpiar Chat"):
        st.session_state.messages = []
        st.rerun()

# Auto-refresh para mantener la conexión WebSocket activa
if st.session_state.ws_connected:
    time.sleep(0.1)  # Pequeña pausa para no sobrecargar
    st.rerun()