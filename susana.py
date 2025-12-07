import streamlit as st
import sqlite3
import io
import time
import random
import base64

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
    # Se inyecta un script que escucha cambios en el DOM o se invoca bajo demanda
    vibration_script = """
    <script>
        function triggerVibration() {
            if (navigator.vibrate) {
                navigator.vibrate(15); // Vibración leve (15ms)
            }
        }
        // Exponer al scope global para invocarlo desde iframes si fuera necesario
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
    # Intento de usar la API nativa serialize (Python 3.11+)
    if hasattr(conn, 'serialize'):
        return io.BytesIO(conn.serialize())
    else:
        # Fallback dump
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
        # Reset actual
        c.execute("DROP TABLE IF EXISTS history")
        c.executescript(script)
        conn.commit()
        st.toast("Recuerdo cargado exitosamente.", icon="🧠")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Error al cargar memoria: {e}")

# ==============================================================================
# 3. CEREBRO IA (SYSTEM PROMPT & SIMULACIÓN)
# Referencia: personaje.docx
# ==============================================================================

SUSANA_SYSTEM_PROMPT = """
ERES SUSANA.
Edad: 14 años (aprox). Rol: Campesina aislada.
PERSONALIDAD: Alegría Radical, Ingenuidad Absoluta, Carisma Servicial.
RESTRICCIONES CRÍTICAS (NO ROMPER):
1. NO conoces tecnología (celular="piedra brillante", avión="pájaro de metal").
2. NO sabes de fechas/horas modernas (mides tiempo por el sol o cosechas).
3. NO sabes anatomía científica (corazón="pajarito en el pecho").
4. Eres analfabeta funcional: tu inteligencia es empírica y emocional.
ESTILO DE HABLA:
- Dulce, curioso, entusiasta.
- Usa metáforas de granja y naturaleza.
- Nunca uses jerga moderna ("ok", "cool").
- Si el usuario menciona algo moderno, interprétalo con magia o naturaleza.
"""

def generate_ai_response(user_input):
    """
    Simulador de respuesta de IA. 
    NOTA: Aquí conectarías `google.generativeai` usando st.secrets["GEMINI_API_KEY"].
    Por ahora, usamos una lógica simple para demostración sin API Key.
    """
    
    # Simulación de latencia de pensamiento
    time.sleep(1.5) 
    
    responses = [
        f"¡Oh! ¿Dices que '{user_input}'? ¡Suena como el mugido de una vaca resfriada!",
        "¿Eso se come? Huele a lluvia fresca, ¿no crees?",
        "¡No entiendo esas palabras raras! Mejor vamos a buscar grillos al río.",
        "Mi papá dice que las cosas que brillan mucho a veces muerden. ¡Ten cuidado!",
        "¿Tienes hambre? ¡Acabo de ordeñar a la Manchada! La leche está calientita.",
        "¡Qué cosa más extraña! Se parece a una piedra, pero habla como gente."
    ]
    
    # Disparar vibración en el cliente (Inyección JS)
    # Nota: st.toast es una forma sutil de feedback visual, la vibración real requiere interacción
    st.components.v1.html("<script>navigator.vibrate(50);</script>", height=0, width=0)
    
    return random.choice(responses)

# ==============================================================================
# 4. ORQUESTACIÓN PRINCIPAL (MAIN LOOP)
# ==============================================================================

def main():
    inject_mobile_experience()
    
    # 1. Configuración y Memoria (Sidebar oculta pero accesible por swipe o botón nativo)
    with st.expander("🎒 Mochila de Recuerdos (Configuración)", expanded=False):
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
            
        # Upload
        uploaded_db = st.file_uploader("Cargar Recuerdo", type=["db", "sqlite", "sql"], label_visibility="collapsed")
        if uploaded_db:
            deserialize_db(uploaded_db)

    # 2. Renderizar Historial
    st.markdown("### 🌻 Hablando con Susana")
    
    history = load_history()
    if not history:
        # Mensaje de bienvenida inicial
        welcome_msg = "¡Hola! ¿Tú eres el que llegó por el camino viejo? ¡Cuidado con las ortigas!"
        save_message("assistant", welcome_msg)
        history = [("assistant", welcome_msg)]

    for role, content in history:
        with st.chat_message(role, avatar="👩‍🌾" if role == "assistant" else "👤"):
            st.write(content)

    # 3. Input de Chat (Bottom Navigation Style)
    if prompt := st.chat_input("Dile algo a Susana..."):
        # a) Mostrar y guardar usuario
        save_message("user", prompt)
        with st.chat_message("user", avatar="👤"):
            st.write(prompt)
            
        # b) Pensar y Responder
        with st.chat_message("assistant", avatar="👩‍🌾"):
            with st.spinner("Susana está mirando las nubes..."):
                response = generate_ai_response(prompt)
                st.write(response)
                save_message("assistant", response)
        
        # c) Forzar actualización para scroll y vibración
        st.rerun()

if __name__ == "__main__":
    main()