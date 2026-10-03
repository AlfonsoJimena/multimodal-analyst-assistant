"""Interfaz de chat del agente en Streamlit (P3-12).

    # Desde parte3_agente_conversacional/, con la API (P3-11) en marcha
    streamlit run src/ui/app.py

No tiene logica de negocio: solo llama a POST /chat de la API del agente
(AGENT_API_URL), con la cabecera X-API-Key = AGENT_API_TOKEN. Nunca habla
con el coordinador ni con el LLM.

Estado de la pagina (st.session_state):
  - session_id: identificador de la conversacion, el mismo en todas las
    preguntas; «Nueva conversación» lo regenera y limpia la pantalla.
  - messages:   lo que se ha pintado, para repintarlo en cada rerun. Los
    del asistente guardan la `ChatResponse` completa (bloques, fuentes y
    avisos) para que la interfaz pueda pintarlos (P3-13).
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import streamlit as st

# `streamlit run` solo anade src/ui/ al path: hace falta la raiz de la parte 3
# para importar `src.*` igual que en la API y en los tests.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agent.config import get_config  # noqa: E402
from src.ui import client as agent_client  # noqa: E402

MAX_MESSAGE_CHARS = 2000  # el mismo limite que ChatRequest
EXAMPLES = (
    "¿Cuántos viajes hubo en total?",
    "Compara las tres sedes",
    "¿Cuál es la hora punta de viajes?",
)


# ============================================================
# Estado de la sesion
# ============================================================

def _new_session_id() -> str:
    return uuid.uuid4().hex


def _init_state() -> None:
    if "session_id" not in st.session_state:
        st.session_state.session_id = _new_session_id()
    if "messages" not in st.session_state:
        st.session_state.messages = []


def _new_conversation() -> None:
    """Callback del boton: se ejecuta antes del rerun, con la pantalla aun sin pintar."""
    st.session_state.session_id = _new_session_id()
    st.session_state.messages = []


# ============================================================
# Pintado
# ============================================================

def _render(message: dict) -> None:
    with st.chat_message(message["role"]):
        if message.get("error"):
            st.error(message["content"])
        else:
            st.markdown(message["content"])


def _sidebar() -> None:
    with st.sidebar:
        st.header("Asistente de datos")
        st.caption(
            "Pregunta por los viajes de taxi de las tres sedes: viajes, "
            "ingresos, zonas, métodos de pago o evolución por horas."
        )
        st.button(
            "Nueva conversación",
            on_click=_new_conversation,
            use_container_width=True,
            type="primary",
        )
        st.caption(f"Sesión `{st.session_state.session_id[:8]}`")


def _welcome() -> None:
    examples = "\n".join(f"- {example}" for example in EXAMPLES)
    with st.chat_message("assistant"):
        st.markdown(
            "Hola, soy el asistente de análisis de datos. Puedes preguntarme, "
            f"por ejemplo:\n\n{examples}"
        )


# ============================================================
# Pagina
# ============================================================

def main() -> None:
    st.set_page_config(page_title="Asistente de datos", page_icon="🚕", layout="centered")
    _init_state()
    config = get_config()

    _sidebar()
    st.title("Asistente de análisis de datos")

    _welcome()
    for message in st.session_state.messages:
        _render(message)

    question = st.chat_input("Escribe tu pregunta…", max_chars=MAX_MESSAGE_CHARS)
    if not question:
        return

    user_message = {"role": "user", "content": question}
    st.session_state.messages.append(user_message)
    _render(user_message)

    with st.spinner("Pensando…"):
        reply = agent_client.ask_agent(
            config.agent_api_url,
            config.agent_api_token,
            st.session_state.session_id,
            question,
        )

    if isinstance(reply, agent_client.AgentError):
        answer = {"role": "assistant", "content": reply.message, "error": True}
    else:
        answer = {"role": "assistant", "content": reply.reply, "response": reply}
    st.session_state.messages.append(answer)
    _render(answer)


main()
