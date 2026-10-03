"""Sesiones en memoria de la API del agente (P3-11).

Cada `session_id` guarda los ultimos turnos de la conversacion (solo el
texto del usuario y del asistente, nunca los mensajes de herramientas) y
caduca tras un tiempo sin uso. Todo vive en el proceso: si la API se
reinicia, las conversaciones empiezan de cero.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Callable


class SessionStore:
    """Historial por sesion, con caducidad y limite de sesiones."""

    def __init__(
        self,
        ttl_s: float = 3600.0,
        max_turns: int = 6,
        max_sessions: int = 1000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl_s = ttl_s
        self._max_turns = max_turns
        self._max_sessions = max_sessions
        self._clock = clock
        # session_id -> (mensajes, instante del ultimo uso); el mas antiguo primero.
        self._sessions: "OrderedDict[str, tuple[list[dict], float]]" = OrderedDict()
        self._lock = threading.Lock()

    def history(self, session_id: str) -> list[dict]:
        """Copia del historial de la sesion ([] si no existe o ha caducado)."""
        with self._lock:
            now = self._clock()
            self._sweep(now)
            entry = self._sessions.get(session_id)
            if entry is None:
                return []
            messages, _ = entry
            self._sessions[session_id] = (messages, now)
            self._sessions.move_to_end(session_id)
            return [dict(message) for message in messages]

    def add_turn(self, session_id: str, user: str, assistant: str) -> None:
        """Anade un turno (pregunta y respuesta) y recorta a los ultimos N."""
        if self._max_turns <= 0:
            return
        with self._lock:
            now = self._clock()
            self._sweep(now)
            messages = self._sessions.get(session_id, ([], now))[0]
            messages.append({"role": "user", "content": user})
            messages.append({"role": "assistant", "content": assistant})
            del messages[: -2 * self._max_turns]
            self._sessions[session_id] = (messages, now)
            self._sessions.move_to_end(session_id)
            while len(self._sessions) > self._max_sessions:
                self._sessions.popitem(last=False)

    def __len__(self) -> int:
        with self._lock:
            self._sweep(self._clock())
            return len(self._sessions)

    def _sweep(self, now: float) -> None:
        """Borra las sesiones sin uso desde hace mas de `ttl_s` (con el lock tomado)."""
        expired = [
            session_id
            for session_id, (_, last_used) in self._sessions.items()
            if now - last_used > self._ttl_s
        ]
        for session_id in expired:
            del self._sessions[session_id]
