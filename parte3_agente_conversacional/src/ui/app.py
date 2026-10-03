"""Interfaz de chat del agente en Streamlit (P3-12 y P3-13).

    # Desde parte3_agente_conversacional/, con la API (P3-11) en marcha
    streamlit run src/ui/app.py

No tiene logica de negocio: solo llama a la API del agente (AGENT_API_URL),
con la cabecera X-API-Key = AGENT_API_TOKEN: POST /chat para las preguntas
y GET /status para el estado de la barra lateral. Nunca habla con el
coordinador ni con el LLM.

De cada respuesta pinta el texto, los bloques (métricas, tablas y
gráficos), los avisos y la trazabilidad (ver `render.py`).

Estado de la pagina (st.session_state):
  - session_id: identificador de la conversacion, el mismo en todas las
    preguntas; «Nueva conversación» lo regenera y limpia la pantalla.
  - messages:   lo que se ha pintado, para repintarlo en cada rerun. Los
    del asistente guardan la `ChatResponse` completa.
  - status:     ultimo resultado de /status; «Refrescar» lo vuelve a pedir.
  - pending:    pregunta sugerida pulsada, que se envia en el siguiente rerun.
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
from src.ui import render  # noqa: E402

MAX_MESSAGE_CHARS = 2000  # el mismo limite que ChatRequest

# Una pregunta por caso de uso principal (cada una usa una herramienta distinta).
SUGGESTIONS = (
    "¿Cuántos viajes e ingresos hubo en total?",
    "Compara las tres sedes",
    "¿Cuál fue la hora punta de viajes el último día con datos?",
    "¿Qué zonas de recogida tienen más viajes?",
)
HELP_TEXT = (
    "Hola, soy el asistente de análisis de datos. Respondo con datos agregados "
    "de los viajes de taxi de las tres sedes: viajes, ingresos y medias, "
    "comparativa entre sedes, evolución por hora o por día, zonas de recogida, "
    "métodos de pago y estado de la plataforma.\n\n"
    "No hay viajes individuales, conductores, pasajeros, rutas origen-destino "
    "ni datos de otras ciudades."
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


def _ask_suggestion(question: str) -> None:
    """Callback de una pregunta sugerida: se envia en este mismo rerun."""
    st.session_state.pending = question


def _refresh_status() -> None:
    st.session_state.pop("status", None)


def _load_status(config, force: bool = False):
    if force or "status" not in st.session_state:
        st.session_state.status = agent_client.get_status(
            config.agent_api_url, config.agent_api_token
        )
    return st.session_state.status


# ============================================================
# Pintado
# ============================================================

def _render(message: dict) -> None:
    with st.chat_message(message["role"]):
        if message.get("error"):
            st.error(render.md(message["content"]))
        elif message.get("response") is not None:
            render.render_answer(message["response"])
        else:
            st.markdown(render.md(message["content"]))


def _sidebar(config):
    """Barra lateral; devuelve el hueco del estado para repintarlo si cambia."""
    with st.sidebar:
        st.header("Asistente de datos")
        st.button(
            "Nueva conversación",
            on_click=_new_conversation,
            use_container_width=True,
            type="primary",
        )
        st.caption(f"Sesión `{st.session_state.session_id[:8]}`")

        st.subheader("Estado de la plataforma")
        st.button("Refrescar estado", on_click=_refresh_status, use_container_width=True)
        status_box = st.empty()
    _show_status(status_box, _load_status(config))
    return status_box


def _show_status(status_box, status) -> None:
    with status_box.container():
        render.render_status(status)


def _welcome() -> None:
    with st.chat_message("assistant"):
        st.markdown(HELP_TEXT)
        st.markdown("**Prueba con una de estas preguntas:**")
        for row in range(0, len(SUGGESTIONS), 2):
            for column, question in zip(st.columns(2), SUGGESTIONS[row:row + 2]):
                column.button(
                    question,
                    key=f"sugerencia_{SUGGESTIONS.index(question)}",
                    on_click=_ask_suggestion,
                    args=(question,),
                    use_container_width=True,
                )


# ============================================================
# Pagina
# ============================================================

def main() -> None:
    st.set_page_config(page_title="Asistente de datos", page_icon="🚕", layout="wide")
    _init_state()
    config = get_config()

    status_box = _sidebar(config)
    st.title("Asistente de análisis de datos")

    _welcome()
    for message in st.session_state.messages:
        _render(message)

    typed = st.chat_input("Escribe tu pregunta…", max_chars=MAX_MESSAGE_CHARS)
    question = typed or st.session_state.pop("pending", None)
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

    # Si algo ha fallado (p. ej. una sede caida), el estado de la barra
    # lateral se actualiza ya, sin esperar a que pulsen «Refrescar».
    if isinstance(reply, agent_client.AgentError) or reply.warnings:
        _show_status(status_box, _load_status(config, force=True))


main()
