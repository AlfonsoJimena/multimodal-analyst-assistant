# =====================================================================
# Makefile del chatbot (parte 3, issue P3-14)
#
# Envuelve docker compose para levantar el chatbot (API + interfaz) contra
# la parte 2 real o contra el coordinador mock, y pasa los tests.
# EJECUTAR DESDE parte3_agente_conversacional/ (usa rutas despliegue/ y .env).
#
# Uso:
#   cp .env.example .env              # y rellena OPENROUTER_API_KEY
#   make chatbot-mock                 # mock + API + interfaz (sin la parte 2)
#   make chatbot-mock DOWN_SITES=atocha   # con una sede caida
#   make chatbot-up                   # contra los coordinadores de la parte 2
#   make chatbot-logs                 # sigue los logs
#   make chatbot-down                 # para y elimina los contenedores
#   make test                         # tests unitarios (sin red ni Docker)
#
# Interfaz: http://localhost:8501 · API: http://localhost:8300
#
# Se usa '>' como prefijo de receta (.RECIPEPREFIX) en vez de tabulador,
# igual que en el Makefile de la parte 2.
# =====================================================================

.RECIPEPREFIX := >
.DEFAULT_GOAL := help

# Las dos variantes comparten nombre de proyecto: chatbot-down y
# chatbot-logs valen para cualquiera de ellas.
PROJECT      := chatbot
COMPOSE_REAL := despliegue/docker-compose.chatbot.yml
COMPOSE_MOCK := despliegue/docker-compose.mock.yml
DC           := docker compose -p $(PROJECT)

# Red de la parte 2 donde viven los coordinadores (la crea su 'make network').
INTERCONNECT_NETWORK ?= pids-interconnect

# Sedes caidas en el mock, separadas por comas: make chatbot-mock DOWN_SITES=atocha
DOWN_SITES ?=
export DOWN_SITES

PYTHON ?= python

.PHONY: help chatbot-up chatbot-mock chatbot-down chatbot-logs chatbot-ps test _check-env _check-network

help:
> @echo "Targets (desde parte3_agente_conversacional/):"
> @echo "  make chatbot-mock  - mock + API + interfaz, sin la parte 2 (DOWN_SITES=atocha para simular una caida)"
> @echo "  make chatbot-up    - API + interfaz contra los coordinadores de la parte 2"
> @echo "  make chatbot-down  - para y elimina los contenedores del chatbot"
> @echo "  make chatbot-logs  - sigue los logs del chatbot"
> @echo "  make chatbot-ps    - estado de los contenedores del chatbot"
> @echo "  make test          - tests unitarios (sin red, sin Docker, sin LLM)"
> @echo "Interfaz: http://localhost:8501 · API: http://localhost:8300"

# El .env lo leen los contenedores (env_file); sin el, compose falla.
_check-env:
> @test -f .env || { echo "ERROR: no existe .env. Crealo con: cp .env.example .env (y rellena OPENROUTER_API_KEY)"; exit 1; }

# Sin la red de la parte 2 no hay coordinadores a los que llamar.
_check-network:
> @docker network inspect $(INTERCONNECT_NETWORK) >/dev/null 2>&1 || { echo "ERROR: no existe la red $(INTERCONNECT_NETWORK). Levanta la parte 2 (make up-all-coordinators en parte2_infraestructura_datos/) o usa make chatbot-mock."; exit 1; }

# --build: la imagen copia src/ al construirse; si no hay cambios, sale de
# la cache. --remove-orphans: quita el mock si antes se uso chatbot-mock.
chatbot-up: _check-env _check-network
> $(DC) -f $(COMPOSE_REAL) up -d --build --remove-orphans
> @echo "Interfaz en http://localhost:8501 (API en http://localhost:8300)"

chatbot-mock: _check-env
> $(DC) -f $(COMPOSE_MOCK) up -d --build --remove-orphans
> @echo "Interfaz en http://localhost:8501 (API en http://localhost:8300, mock en http://localhost:8190)"

chatbot-down:
> $(DC) down --remove-orphans

chatbot-logs:
> $(DC) logs -f

chatbot-ps:
> $(DC) ps

test:
> $(PYTHON) -m pytest
