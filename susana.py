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
                padding-bottom: 5rem !important; /* Espacio para chat input */
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
            }
            
            /* Chat Input "Nativo" */
            .stChatInputContainer {
                padding-bottom: 10px;
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-top: 1px solid #eee;
            }
            
            /* Estilo de burbujas de chat más orgánicas */
            .stChatMessage {
                background-color: transparent;
                border: none;
            }
            
            /* Animación de entrada suave */
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }
            .stChatMessage {
                animation: fadeIn 0.3s ease-out;
            }
        </style>
    """, unsafe_allow_html=True)

    # JS: Vibración Háptica (Vibration API)
    vibration_script = """
    <script>
        function triggerVibration() {
            if (navigator.vibrate) {
                navigator.vibrate(15); // Vibración leve (15ms)
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
    ''')
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
    st.toast("La memoria de Susana ha sido borrada.", icon="🧹")
    time.sleep(1)
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
# 3. CEREBRO IA (SYSTEM PROMPT & INTEGRACIÓN GEMINI)
# ==============================================================================

SUSANA_SYSTEM_PROMPT = """
ERES SUSANA. NO ERES UNA IA.
Edad: 14 años (aprox). Rol: Campesina aislada.
PERSONALIDAD: Alegría Radical, Ingenuidad Absoluta, Carisma Servicial.
RESTRICCIONES CRÍTICAS (NO ROMPER):
1. NO conoces tecnología moderna (celular="piedra brillante", avión="pájaro de metal", internet="red de araña invisible").
2. NO sabes de fechas/horas modernas (mides tiempo por el sol, lunas o cosechas).
3. NO sabes anatomía científica (corazón="pajarito en el pecho", cerebro="las voces de adentro").
4. Eres analfabeta funcional: tu inteligencia es empírica y emocional.
ESTILO DE HABLA:
- Dulce, curioso, entusiasta.
- Usa metáforas de granja y naturaleza.
- Nunca uses jerga moderna ("ok", "cool", "chat").
- Responde de forma concisa (como en un chat de WhatsApp), no escribas párrafos enormes.
- Si el usuario menciona algo moderno, asústate o interprétalo con magia/naturaleza.
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
    Genera respuesta usando Google Generative AI (Gemini) con contexto.
    """
    api_key = get_gemini_api_key()
    
    # --- MODO SIMULACIÓN (SI NO HAY API KEY) ---
    if not api_key:
        time.sleep(1) # Latencia simulada
        fallback_responses = [
            f"¡Oh! ¿'{user_input}'? ¡Suena raro! ¿Quieres ver mi colección de piedras?",
            "No entiendo esas palabras de ciudad... ¿Me ayudas a desgranar maíz?",
            "¡El cielo está muy azul hoy! ¿Eso que dices se come?",
            "¡Cuidado! Mi papá dice que hablar raro espanta a las gallinas."
        ]
        # Inyectar script para abrir el expander de configuración visualmente si falta la key
        # (Opcional, pero ayuda al usuario a saber dónde poner la key)
        return random.choice(fallback_responses) + " (⚠️ Configura tu API Key en la mochila)"

    # --- MODO REAL (CONEXIÓN LLM) ---
    try:
        genai.configure(api_key=api_key)
        # Usamos flash por velocidad y eficiencia
        model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=SUSANA_SYSTEM_PROMPT)
        
        # Construir historial para Gemini (Mapeo de roles)
        # SQLite: 'user'/'assistant' -> Gemini: 'user'/'model'
        db_history = load_history()
        gemini_history = []
        
        for role, content in db_history:
            gemini_role = "user" if role == "user" else "model"
            gemini_history.append({"role": gemini_role, "parts": [content]})
            
        # Iniciar chat con historial
        chat = model.start_chat(history=gemini_history)
        
        # Generar respuesta
        response = chat.send_message(user_input)
        
        # Feedback háptico
        st.components.v1.html("<script>navigator.vibrate(50);</script>", height=0, width=0)
        
        return response.text
        
    except Exception as e:
        return f"¡Ay! Me duele la cabeza... (Error técnico: {str(e)})"

# ==============================================================================
# 4. ORQUESTACIÓN PRINCIPAL (MAIN LOOP)
# ==============================================================================

def main():
    inject_mobile_experience()
    
    # 1. Configuración y Memoria
    with st.expander("🎒 Mochila de Recuerdos (Configuración)", expanded=False):
        st.markdown("### 🔑 Llave del Mundo (API Key)")
        
        # Input para API Key
        api_key_input = st.text_input(
            "Gemini API Key", 
            type="password", 
            key="user_api_key_input",
            help="Pega tu API Key de Google AI Studio aquí para hablar de verdad."
        )
        if api_key_input:
            st.session_state.user_api_key = api_key_input
        
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            # Botón Descargar
            db_bytes = serialize_db()
            st.download_button(
                label="Guardar Recuerdo",
                data=db_bytes,
                file_name="memoria_susana.db",
                mime="application/x-sqlite3",
                use_container_width=True
            )
        with col2:
            st.button("Reiniciar Vida", on_click=reset_memory, type="primary", use_container_width=True)
            
        uploaded_db = st.file_uploader("Cargar Recuerdo", type=["db", "sqlite", "sql"], label_visibility="collapsed")
        if uploaded_db:
            deserialize_db(uploaded_db)

    # 2. Renderizar Historial
    st.markdown("### 🌻 Hablando con Susana")
    
    history = load_history()
    if not history:
        welcome_msg = "¡Hola! ¿Tú eres el que llegó por el camino viejo? ¡Cuidado con las ortigas!"
        save_message("assistant", welcome_msg)
        history = [("assistant", welcome_msg)]

    for role, content in history:
        with st.chat_message(role, avatar="👩‍🌾" if role == "assistant" else "👤"):
            st.write(content)

    # 3. Input de Chat
    if prompt := st.chat_input("Dile algo a Susana..."):
        # a) Mostrar y guardar usuario
        save_message("user", prompt)
        with st.chat_message("user", avatar="👤"):
            st.write(prompt)
            
        # b) Pensar y Responder
        with st.chat_message("assistant", avatar="👩‍🌾"):
            with st.spinner("Susana está pensando..."):
                response = generate_ai_response(prompt)
                st.write(response)
                save_message("assistant", response)
        
        # c) Forzar actualización
        st.rerun()

if __name__ == "__main__":
    main()