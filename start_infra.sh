#!/usr/bin/env bash

set -e

# ============================================================
# Arranque de la Parte 2 - Infraestructura de datos
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PART2_DIR="$SCRIPT_DIR/parte2_infraestructura_datos"
VENV_DIR="$PART2_DIR/.venv"

# Colores
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
BLUE="\033[0;34m"
NC="\033[0m"

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
# 1. Comprobar directorio de la Parte 2
# ------------------------------------------------------------

if [ ! -d "$PART2_DIR" ]; then
    error "No se encuentra $PART2_DIR"
fi

cd "$PART2_DIR"

info "Directorio de trabajo: $PART2_DIR"

# ------------------------------------------------------------
# 2. Comprobar Python
# ------------------------------------------------------------

if ! command -v python3 >/dev/null 2>&1; then
    error "python3 no está instalado."
fi

ok "Python encontrado: $(python3 --version)"

# ------------------------------------------------------------
# 3. Crear / activar entorno virtual
# ------------------------------------------------------------

if [ ! -d "$VENV_DIR" ]; then
    info "No existe el entorno virtual. Creando .venv..."
    python3 -m venv "$VENV_DIR"
    ok "Entorno virtual creado."
else
    ok "Entorno virtual encontrado."
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

ok "Entorno virtual activado."

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
    warn "No se ha encontrado requirements-dev.txt ni requirements.txt."
fi

ok "Dependencias instaladas."

# ------------------------------------------------------------
# 5. Comprobar Docker
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
# 6. Levantar la infraestructura
# ------------------------------------------------------------

echo
info "Levantando Central, Chamartín y Atocha con sus coordinadores..."
echo

make up-all-coordinators

echo
info "Levantando monitorización central (Prometheus + Grafana)..."
docker compose -f deploy/docker-compose.central.yml up -d

echo
ok "Comando de arranque completado."

# ------------------------------------------------------------
# 7. Esperar a los coordinadores
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

wait_for_url "Coordinador Central"   "http://localhost:8100/health" || true
wait_for_url "Coordinador Chamartín" "http://localhost:8101/health" || true
wait_for_url "Coordinador Atocha"    "http://localhost:8102/health" || true

wait_for_url "API Central"   "http://localhost:8000/health" || true
wait_for_url "API Chamartín" "http://localhost:8001/health" || true
wait_for_url "API Atocha"    "http://localhost:8002/health" || true

wait_for_url "Prometheus" "http://localhost:9090/-/ready" || true
wait_for_url "Grafana"    "http://localhost:3000/api/health" || true

# ------------------------------------------------------------
# 8. Mostrar estado Docker
# ------------------------------------------------------------

echo
echo "============================================================"
echo " Estado de los contenedores"
echo "============================================================"
echo

docker ps \
    --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" \
    | grep -E "NAMES|central|chamartin|atocha" || true

# ------------------------------------------------------------
# 9. Mostrar enlaces
# ------------------------------------------------------------

echo
echo "============================================================"
echo -e "${GREEN} Parte 2 levantada${NC}"
echo "============================================================"
echo

echo "Monitorización:"
echo "  Grafana:      http://localhost:3000"
echo "  Prometheus:   http://localhost:9090"
echo
echo "Coordinadores:"
echo "  Central:      http://localhost:8100"
echo "  Chamartín:    http://localhost:8101"
echo "  Atocha:       http://localhost:8102"
echo
echo "APIs de sede:"
echo "  Central:      http://localhost:8000"
echo "  Chamartín:    http://localhost:8001"
echo "  Atocha:       http://localhost:8002"
echo
echo "Comandos útiles:"
echo "  make failover-check"
echo "  make ps SITE=central"
echo "  make ps SITE=chamartin"
echo "  make ps SITE=atocha"
echo "  make down-all"
echo

# ------------------------------------------------------------
# 10. Opción para abrir Grafana y Prometheus
# ------------------------------------------------------------

if [ "${1:-}" = "--open" ]; then
    if command -v xdg-open >/dev/null 2>&1; then
        info "Abriendo Grafana y Prometheus en el navegador..."
        xdg-open "http://localhost:3000" >/dev/null 2>&1 &
        xdg-open "http://localhost:9090" >/dev/null 2>&1 &
    else
        warn "xdg-open no está disponible."
    fi
fi

