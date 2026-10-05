#!/usr/bin/env bash

set -e

# ============================================================
# Arranque de la Parte 3 - Agente conversacional
#
# Uso:
#   ./start_chatbot.sh
#   ./start_chatbot.sh --mock
#   ./start_chatbot.sh --open
#   ./start_chatbot.sh --mock --open
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PART3_DIR="$SCRIPT_DIR/parte3_agente_conversacional"

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
BLUE="\033[0;34m"
NC="\033[0m"

MODE="real"
OPEN_BROWSER=false

# ------------------------------------------------------------
# Funciones
# ------------------------------------------------------------

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

ok() {
    echo -e "${GREEN}[OK]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[AVISO]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# ------------------------------------------------------------
# Argumentos
# ------------------------------------------------------------

for arg in "$@"; do
    case "$arg" in
        --mock)
            MODE="mock"
            ;;
        --open)
            OPEN_BROWSER=true
            ;;
        --help|-h)
            echo "Uso:"
            echo "  ./start_chatbot.sh          Parte 2 real"
            echo "  ./start_chatbot.sh --mock   Coordinador mock"
            echo "  ./start_chatbot.sh --open   Abre Streamlit en el navegador"
            echo "  ./start_chatbot.sh --mock --open"
            exit 0
            ;;
        *)
            error "Argumento desconocido: $arg"
            ;;
    esac
done

# ------------------------------------------------------------
# 1. Comprobar directorio
# ------------------------------------------------------------

if [ ! -d "$PART3_DIR" ]; then
    error "No se encuentra $PART3_DIR"
fi

cd "$PART3_DIR"

info "Directorio de trabajo: $PART3_DIR"

# ------------------------------------------------------------
# 2. Comprobar Python
# ------------------------------------------------------------

if ! command -v python3 >/dev/null 2>&1; then
    error "python3 no está instalado."
fi

ok "Python encontrado: $(python3 --version)"

# ------------------------------------------------------------
# 3. Crear / activar entorno virtual
#
# Si ya existe 'venv', lo reutiliza.
# Si existe '.venv', también.
# Si no existe ninguno, crea '.venv'.
# ------------------------------------------------------------

if [ -d ".venv" ]; then
    VENV_DIR="$PART3_DIR/.venv"
elif [ -d "venv" ]; then
    VENV_DIR="$PART3_DIR/venv"
else
    VENV_DIR="$PART3_DIR/.venv"

    info "No existe entorno virtual. Creando .venv..."
    python3 -m venv "$VENV_DIR"
    ok "Entorno virtual creado."
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

ok "Entorno virtual activado: $VENV_DIR"

# ------------------------------------------------------------
# 4. Instalar dependencias
# ------------------------------------------------------------

info "Comprobando dependencias..."

python -m pip install --upgrade pip >/dev/null

if [ -f requirements-dev.txt ]; then
    python -m pip install -r requirements-dev.txt
elif [ -f requirements.txt ]; then
    python -m pip install -r requirements.txt
else
    error "No se encuentra requirements-dev.txt ni requirements.txt."
fi

ok "Dependencias instaladas."

# ------------------------------------------------------------
# 5. Comprobar .env
# ------------------------------------------------------------

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        warn "No existe .env."
        info "Creando .env a partir de .env.example..."
        cp .env.example .env

        echo
        warn "Se ha creado parte3_agente_conversacional/.env"
        warn "Debes editarlo y rellenar OPENROUTER_API_KEY antes de usar el chatbot."
        echo
        echo "Edita:"
        echo "  $PART3_DIR/.env"
        echo
        exit 1
    else
        error "No existe .env ni .env.example."
    fi
fi

ok "Fichero .env encontrado."

OPENROUTER_KEY="$(
    sed -nE 's/^[[:space:]]*OPENROUTER_API_KEY[[:space:]]*=[[:space:]]*(.*)$/\1/p' .env \
    | tail -n 1
)"

OPENROUTER_KEY="${OPENROUTER_KEY%\"}"
OPENROUTER_KEY="${OPENROUTER_KEY#\"}"
OPENROUTER_KEY="${OPENROUTER_KEY%\'}"
OPENROUTER_KEY="${OPENROUTER_KEY#\'}"

if [ -z "$OPENROUTER_KEY" ]; then
    error "OPENROUTER_API_KEY no está configurada en .env."
fi

if [ "$OPENROUTER_KEY" = "sk-or-..." ]; then
    error "OPENROUTER_API_KEY sigue teniendo el valor de ejemplo. Edita .env."
fi

ok "OPENROUTER_API_KEY está configurada."

# ------------------------------------------------------------
# 6. Comprobar Docker
# ------------------------------------------------------------

if ! command -v docker >/dev/null 2>&1; then
    error "Docker no está instalado."
fi

if ! docker info >/dev/null 2>&1; then
    error "Docker no está arrancado o el usuario no tiene permisos."
fi

ok "Docker está disponible."

if ! docker compose version >/dev/null 2>&1; then
    error "Docker Compose v2 no está disponible."
fi

ok "Docker Compose está disponible."

# ------------------------------------------------------------
# 7. Comprobar Parte 2 si usamos infraestructura real
# ------------------------------------------------------------

if [ "$MODE" = "real" ]; then

    info "Modo: infraestructura real de la Parte 2"

    if ! docker network inspect pids-interconnect >/dev/null 2>&1; then
        error "No existe la red pids-interconnect. Ejecuta primero ./start_infra.sh"
    fi

    CENTRAL_OK=false
    CHAMARTIN_OK=false
    ATOCHA_OK=false

    if curl -fsS http://localhost:8100/health >/dev/null 2>&1; then
        CENTRAL_OK=true
    fi

    if curl -fsS http://localhost:8101/health >/dev/null 2>&1; then
        CHAMARTIN_OK=true
    fi

    if curl -fsS http://localhost:8102/health >/dev/null 2>&1; then
        ATOCHA_OK=true
    fi

    if [ "$CENTRAL_OK" = false ] &&
       [ "$CHAMARTIN_OK" = false ] &&
       [ "$ATOCHA_OK" = false ]; then

        error "No responde ningún coordinador de la Parte 2. Ejecuta primero ./start_infra.sh"
    fi

    [ "$CENTRAL_OK" = true ] \
        && ok "Coordinador Central disponible." \
        || warn "Coordinador Central no responde."

    [ "$CHAMARTIN_OK" = true ] \
        && ok "Coordinador Chamartín disponible." \
        || warn "Coordinador Chamartín no responde."

    [ "$ATOCHA_OK" = true ] \
        && ok "Coordinador Atocha disponible." \
        || warn "Coordinador Atocha no responde."

else

    info "Modo: coordinador mock"

fi

# ------------------------------------------------------------
# 8. Levantar chatbot
# ------------------------------------------------------------

echo

if [ "$MODE" = "mock" ]; then

    info "Levantando mock + API + interfaz..."
    make chatbot-mock

else

    info "Levantando API + interfaz contra la Parte 2..."
    make chatbot-up

fi

# ------------------------------------------------------------
# 9. Esperar a la API
# ------------------------------------------------------------

wait_for_url() {
    local name="$1"
    local url="$2"
    local attempts=30

    printf "Esperando a %-25s " "$name"

    for ((i=1; i<=attempts; i++)); do

        if curl -fsS "$url" >/dev/null 2>&1; then
            echo -e "${GREEN}OK${NC}"
            return 0
        fi

        sleep 2
        printf "."
    done

    echo
    warn "$name no ha respondido todavía en $url"
    return 1
}

echo
info "Comprobando servicios..."

wait_for_url "API del chatbot" "http://localhost:8300/health" || true
wait_for_url "Interfaz Streamlit" "http://localhost:8501" || true

if [ "$MODE" = "mock" ]; then
    wait_for_url "Coordinador mock" "http://localhost:8190/health" || true
fi

# ------------------------------------------------------------
# 10. Estado de contenedores
# ------------------------------------------------------------

echo
echo "============================================================"
echo " Estado de la Parte 3"
echo "============================================================"
echo

docker compose -p chatbot ps || true

# ------------------------------------------------------------
# 11. Enlaces
# ------------------------------------------------------------

echo
echo "============================================================"
echo -e "${GREEN} Parte 3 levantada${NC}"
echo "============================================================"
echo

echo "Chatbot:"
echo "  Interfaz:     http://localhost:8501"
echo "  API:          http://localhost:8300"
echo "  Health:       http://localhost:8300/health"
echo "  Status:       http://localhost:8300/status"
echo

if [ "$MODE" = "mock" ]; then
    echo "Datos:"
    echo "  Mock:         http://localhost:8190"
    echo
else
    echo "Coordinadores:"
    echo "  Central:      http://localhost:8100"
    echo "  Chamartín:    http://localhost:8101"
    echo "  Atocha:       http://localhost:8102"
    echo
fi

echo "Comandos útiles:"
echo "  cd parte3_agente_conversacional"
echo "  make chatbot-logs"
echo "  make chatbot-ps"
echo "  make chatbot-down"
echo

if [ "$MODE" = "real" ]; then
    echo "Modo utilizado: Parte 2 real"
else
    echo "Modo utilizado: mock"
fi

echo

# ------------------------------------------------------------
# 12. Abrir navegador
# ------------------------------------------------------------

if [ "$OPEN_BROWSER" = true ]; then

    if command -v xdg-open >/dev/null 2>&1; then

        info "Abriendo el chatbot en el navegador..."

        xdg-open "http://localhost:8501" >/dev/null 2>&1 &

    else

        warn "xdg-open no está disponible."

    fi
fi
