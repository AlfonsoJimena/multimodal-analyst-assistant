#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PART2_DIR="$SCRIPT_DIR/parte2_infraestructura_datos"
PART3_DIR="$SCRIPT_DIR/parte3_agente_conversacional"

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

# ------------------------------------------------------------
# Parte 3
# ------------------------------------------------------------

if [ -d "$PART3_DIR" ]; then
    info "Parando Parte 3 (chatbot)..."

    cd "$PART3_DIR"

    if [ -f Makefile ]; then
        make chatbot-down || warn "No se pudo parar la Parte 3 con make chatbot-down."
    else
        warn "No se encontró el Makefile de la Parte 3."
    fi

    ok "Parte 3 parada."
else
    warn "No se encontró $PART3_DIR"
fi

# ------------------------------------------------------------
# Parte 2 - monitorización
# ------------------------------------------------------------

if [ -d "$PART2_DIR" ]; then
    cd "$PART2_DIR"

    info "Parando Grafana y Prometheus..."

    if [ -f deploy/docker-compose.central.yml ]; then
        docker compose -f deploy/docker-compose.central.yml down \
            || warn "No se pudo parar la monitorización."
    else
        warn "No se encontró deploy/docker-compose.central.yml."
    fi

    ok "Monitorización parada."

    # --------------------------------------------------------
    # Parte 2 - sedes y coordinadores
    # --------------------------------------------------------

    info "Parando Central, Chamartín y Atocha..."

    if [ -f Makefile ]; then
        make down-all || warn "No se pudo parar completamente la Parte 2."
    else
        warn "No se encontró el Makefile de la Parte 2."
    fi

    ok "Parte 2 parada."
else
    warn "No se encontró $PART2_DIR"
fi

# ------------------------------------------------------------
# Estado final
# ------------------------------------------------------------

echo
echo "============================================================"
echo " Contenedores Docker que siguen activos"
echo "============================================================"
echo

RUNNING="$(docker ps --format '{{.Names}}')"

if [ -z "$RUNNING" ]; then
    ok "No queda ningún contenedor Docker activo."
else
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo
    warn "Quedan contenedores activos. Pueden pertenecer a otros proyectos."
fi

echo
echo "============================================================"
echo -e "${GREEN} Infraestructura detenida${NC}"
echo "============================================================"
echo
echo "No se han eliminado volúmenes ni datos persistentes."
