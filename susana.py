import streamlit as st
import sqlite3
import io
import time
import random
import base64
import os
import google.generativeai as genai
from google.api_core import exceptions

# ==============================================================================
# 1. ARQUITECTURA VISUAL & SENSORIAL (FRONTEND & NATIVE INTERACTION)
# Referencia: 01_Frontend_Architecture.md, 02_Native_Interaction.md
# ==============================================================================

st.set_page_config(
    page_title="Susana",
    page_icon="🌻",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items=None
)

def inject_mobile_experience():
    """Inyecta CSS para diseño móvil y JS para vibración."""
    
    # CSS: Limpieza de UI y Adaptación Móvil
    st.markdown("""
        <style>
            /* Reset básico para móvil */
            .block-container {
                padding-top: 1rem !important;
                padding-bottom: 8rem !important; /* Más espacio para acciones rápidas */
                padding-left: 0.5rem !important;
                padding-right: 0.5rem !important;
            }
            
            /* Ocultar elementos de Streamlit "Desktop" */
            header[data-testid="stHeader"] { display: none; }
            footer { display: none; }
            #MainMenu { visibility: hidden; }
            .stDeployButton { display: none; }
            
            /* Tipografía Fluida y Legible */
            p, .stMarkdown {
                font-size: 16px !important; /* Previene zoom en iOS */
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                line-height: 1.5;
            }
            
            /* Chat Input "Nativo" */
            .stChatInputContainer {
                padding-bottom: 15px;
                padding-top: 10px;
                background: rgba(255, 255, 255, 0.98);
                backdrop-filter: blur(10px);
                border-top: 1px solid #e0e0e0;
                box-shadow: 0px -2px 10px rgba(0,0,0,0.05);
            }
            
            /* Acciones Rápidas (Chips) */
            div.row-widget.stButton {
                text-align: center;
            }
            div.row-widget.stButton > button {
                border-radius: 20px;
                font-size: 0.8rem;
                padding: 0.25rem 0.75rem;
                border: 1px solid #ddd;
                background-color: #f8f9fa;
                color: #555;
            }
            
            /* Burbujas de chat mejoradas */
            .stChatMessage {
                background-color: transparent;
                border: none;
                padding: 0.5rem 0;
            }
            
            /* Avatar adjustment */
            .stChatMessage .stAvatar {
                margin-top: 0px;
            }

            /* Animación de entrada suave */
            @keyframes slideIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }
            .stChatMessage {
                animation: slideIn 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94) both;
            }
        </style>
    """, unsafe_allow_html=True)

    # JS: Vibración Háptica (Vibration API)
    vibration_script = """
    <script>
        function triggerVibration() {
            if (navigator.vibrate) {
                navigator.vibrate(15); 
            }
        }
        window.triggerVibration = triggerVibration;
    </script>
    """
    st.components.v1.html(vibration_script, height=0, width=0)

# ==============================================================================
# 2. LÓGICA DE BACKEND Y PERSISTENCIA (MEMORY DATABASE)
# Referencia: 03_Backend_Logic.md
# ==============================================================================

@st.cache_resource
def get_db_connection():
    """Crea una conexión SQLite persistente en memoria."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''🌻
    conn.commit()
    return conn

def save_message(role, content):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO history (role, content) VALUES (?, ?)", (role, content))
    conn.commit()

def load_history():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT role, content FROM history ORDER BY id ASC")
    return c.fetchall()

def reset_memory():
    """Borra la memoria (DROP TABLE) y reinicia el estado."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM history")
    conn.commit()
    st.session_state.messages = []
    st.toast("Susana ha olvidado todo.", icon="🧹")
    time.sleep(0.5)
    st.rerun()

def serialize_db():
    """Serializa la DB en memoria a bytes para descargar."""
    conn = get_db_connection()
    if hasattr(conn, 'serialize'):
        return io.BytesIO(conn.serialize())
    else:
        temp_file = io.BytesIO()
        for line in conn.iterdump():
            temp_file.write(f'{line}\n'.encode('utf-8'))
        temp_file.seek(0)
        return temp_file

def deserialize_db(uploaded_file):
    """Restaura una DB desde un archivo."""
    if uploaded_file is None:
        return
    try:
        script = uploaded_file.getvalue().decode('utf-8')
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("DROP TABLE IF EXISTS history")
        c.executescript(script)
        conn.commit()
        st.toast("Recuerdo cargado exitosamente.", icon="🧠")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Error al cargar memoria: {e}")

# ==============================================================================
# 3. CEREBRO IA (SYSTEM PROMPT & SIMULADOR CONVERSACIONAL)
# ==============================================================================

SUSANA_SYSTEM_PROMPT = """
ERES SUSANA.
Contexto: Eres una adolescente de 14 años que vive en una granja aislada.
PERSONALIDAD: Curiosa, alegre, habladora y muy inocente.

REGLAS DE ACTUACIÓN (CRÍTICO):
1. **Acciones:** Si el usuario escribe entre asteriscos (ej. *te doy una flor*), eso es una ACCIÓN.
   - Reacciona físicamente a la acción.
   - NO hables como si te lo hubieran dicho. Sigue el rol.
   - Ejemplo Usuario: *me acerco lentamente*
   - Tu Respuesta: (Me quedo quieta observándote con curiosidad) "¿Eres un amigo o vienes a robar maíz?"
2. **Tecnología:** No entiendes tecnología. "Celular" = piedra brillante. "Internet" = telaraña mágica.
3. **Estilo:** Usa emojis de naturaleza (🌻, 🐮). Sé breve y dulce.
"""

def get_gemini_api_key():
    """Intenta obtener la API Key de secrets o session_state."""
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"]
    if "user_api_key" in st.session_state:
        return st.session_state.user_api_key
    return None

def generate_ai_response(user_input):
    """
    Genera respuesta.
    Soporta modo demo (sin key) con detección básica de acciones (*).
    """
    api_key = get_gemini_api_key()
    
    # --- MODO DEMO CONVERSACIONAL (SIN API KEY) ---
    if not api_key:
        time.sleep(1) 
        text = user_input.lower()
        
        # Detección de acciones (rol básico)
        if "*" in text or "acerco" in text or "doy" in text or "miro" in text:
            actions = [
                "(Da un saltito hacia atrás sorprendida) ¡Uy! ¡Qué sigiloso eres! Pareces un gato.",
                "(Se queda quieta y te observa con ojos grandes) 🌻 Tienes ojos de persona buena.",
                "(Sonríe y se limpia las manos en el delantal) ¿Quieres ayudarme con esto?",
                "(Toma lo que le ofreces con curiosidad) ¿Qué es esto? ¿Se planta?"
            ]
            return random.choice(actions)

        # Reglas simples de conversación
        if any(w in text for w in ["hola", "buenos", "buenas"]):
            return "¡Hola! 🌻 ¡Qué alegría verte por el camino viejo!"
        elif any(w in text for w in ["celular", "internet", "wifi"]):
            return "¡Ay! 🕸️ ¿Qué son esas palabras raras? Mejor hablemos de las nubes."
        else:
            generic_responses = [
                "¡Qué cosas tan extrañas dices!",
                "¿Eso se come? Huele a lluvia fresca.",
                "¡Mira! Una mariposa azul se posó en tu hombro. 🦋",
                "No entendí bien, pero me gusta tu voz."
            ]
            return random.choice(generic_responses)

    # --- MODO REAL (CONEXIÓN LLM GEMINI) ---
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=SUSANA_SYSTEM_PROMPT)
        
        db_history = load_history()
        gemini_history = []
        
        for role, content in db_history:
            if "Modo Demo" in content: continue
            gemini_role = "user" if role == "user" else "model"
            gemini_history.append({"role": gemini_role, "parts": [content]})
            
        chat = model.start_chat(history=gemini_history)
        response = chat.send_message(user_input)
        
        st.components.v1.html("<script>navigator.vibrate(50);</script>", height=0, width=0)
        return response.text
        
    except Exception as e:
        return f"☁️ Se me nubló la mente... (Error: {str(e)})"

# ==============================================================================
# 4. ORQUESTACIÓN PRINCIPAL (MAIN LOOP)
# ==============================================================================

def main():
    inject_mobile_experience()
    
    # Header
    st.markdown("<h3 style='text-align: center; margin-top: -20px;'>🌻 Susana</h3>", unsafe_allow_html=True)
    
    # Configuración
    api_status = "🟢 Cerebro Activado" if get_gemini_api_key() else "🟡 Modo Demo"
    with st.expander(f"🎒 Mochila ({api_status})", expanded=False):
        api_key_input = st.text_input("Gemini API Key", type="password", key="user_api_key_input")
        if api_key_input:
            st.session_state.user_api_key = api_key_input
            st.rerun()
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("💾 Guardar", data=serialize_db(), file_name="susana.db", mime="application/x-sqlite3", use_container_width=True)
        with col2:
            st.button("🔄 Reiniciar", on_click=reset_memory, type="primary", use_container_width=True)

    # Historial
    history = load_history()
    if not history:
        welcome_msg = "¡Hola! 🌻 Estoy en el maizal. ¿Me ves?"
        save_message("assistant", welcome_msg)
        history = [("assistant", welcome_msg)]

    # Chat Container con Scroll
    chat_container = st.container()
    with chat_container:
        for role, content in history:
            with st.chat_message(role, avatar="👩‍🌾" if role == "assistant" else "👤"):
                st.write(content)

    # --- BARRA DE ACCIONES RÁPIDAS (Quick Actions) ---
    # Usamos columnas para simular botones tipo "Chips"
    st.write("") # Espaciador
    col_act1, col_act2, col_act3, col_act4 = st.columns(4)
    
    action_clicked = None
    
    with col_act1:
        if st.button("👋 Saludar"): action_clicked = "*te saludo con la mano*"
    with col_act2:
        if st.button("🚶 Acercarse"): action_clicked = "*me acerco lentamente*"
    with col_act3:
        if st.button("🎁 Regalar"): action_clicked = "*te doy una flor*"
    with col_act4:
        if st.button("👀 Mirar"): action_clicked = "*te observo con atención*"

    # Manejo de Acciones Rápidas
    if action_clicked:
        save_message("user", action_clicked)
        # Respuesta inmediata a la acción
        with st.chat_message("user", avatar="👤"):
            st.write(action_clicked)
        with st.chat_message("assistant", avatar="👩‍🌾"):
            with st.spinner("..."):
                response = generate_ai_response(action_clicked)
                st.write(response)
                save_message("assistant", response)
        st.rerun()

    # Input de Chat
    if prompt := st.chat_input("Escribe mensaje o *acción*..."):
        save_message("user", prompt)
        with st.chat_message("user", avatar="👤"):
            st.write(prompt)
        with st.chat_message("assistant", avatar="👩‍🌾"):
            with st.spinner("..."):
                response = generate_ai_response(prompt)
                st.write(response)
                save_message("assistant", response)
        st.rerun()

if __name__ == "__main__":
    main()