# =====================================================================
# Makefile de despliegue de sedes (issue #64)
#
# Envuelve docker compose para levantar/parar una sede con su .env.
# EJECUTAR DESDE parte2_infraestructura_datos/ (usa rutas deploy/ y sites/).
#
# Uso:
#   make up SITE=chamartin
#   make logs SITE=atocha
#   make down SITE=central
#   make up-all                 # las tres sedes
#   make up-coordinator SITE=chamartin     # sede + coordinator (profile coordinator)
#   make up-all-coordinators               # las tres sedes con coordinator (#59)
#   make stop-coordinator SITE=central     # demo de failover
#   make failover-check                    # que replica responde (central->chamartin->atocha)
#
# Se usa '>' como prefijo de receta (.RECIPEPREFIX) en vez de tabulador,
# para evitar problemas de tabs/espacios al editar.
# =====================================================================

.RECIPEPREFIX := >
.DEFAULT_GOAL := help

# Sede por defecto; sobreescribible: make up SITE=atocha
SITE ?= chamartin

COMPOSE_FILE := deploy/docker-compose.site.yml
ENV_FILE     := sites/$(SITE).env
DC           := docker compose -p $(SITE) --env-file $(ENV_FILE) -f $(COMPOSE_FILE)
# Igual que DC pero incluyendo el profile del coordinator: down/ps/logs
# deben ver tambien ese contenedor si esta levantado.
DC_ALL       := $(DC) --profile coordinator

# Red docker compartida entre sedes (site_api + coordinator), declarada
# como externa en docker-compose.site.yml.
INTERCONNECT_NETWORK ?= pids-interconnect

PYTHON ?= python

# Sedes usadas por los targets *-all
SITES := central chamartin atocha

.PHONY: help config build up down restart logs ps clean network up-coordinator stop-coordinator up-all up-all-coordinators down-all failover-check _check-env

help:
> @echo "Targets (usa SITE=<central|chamartin|atocha>, por defecto: $(SITE)):"
> @echo "  make config   - valida y muestra la config resuelta de la sede"
> @echo "  make build    - construye las imagenes de la sede"
> @echo "  make up       - levanta la sede en segundo plano"
> @echo "  make down     - para y elimina los contenedores de la sede"
> @echo "  make restart  - down + up"
> @echo "  make logs     - sigue los logs de la sede"
> @echo "  make ps       - estado de los servicios de la sede"
> @echo "  make clean    - down + elimina volumenes (BORRA datos)"
> @echo "  make network  - crea la red compartida $(INTERCONNECT_NETWORK) (lo hace 'up' solo)"
> @echo "  make up-coordinator   - levanta la sede incluyendo su coordinator"
> @echo "  make stop-coordinator - para solo el coordinator de la sede (demo failover)"
> @echo "  make up-all / make down-all - todas las sedes ($(SITES))"
> @echo "  make up-all-coordinators    - todas las sedes, cada una con su coordinator"
> @echo "  make failover-check  - consulta el coordinator con failover central->chamartin->atocha"

# Comprueba que existe el .env de la sede antes de actuar
_check-env:
> @test -f $(ENV_FILE) || { echo "ERROR: no existe $(ENV_FILE). SITE='$(SITE)' no es una sede valida ($(SITES))."; exit 1; }

# Crea la red compartida si no existe (idempotente)
network:
> @docker network inspect $(INTERCONNECT_NETWORK) >/dev/null 2>&1 || docker network create $(INTERCONNECT_NETWORK)

config: _check-env
> $(DC_ALL) config

build: _check-env
> $(DC_ALL) build

# --build: las imagenes copian src/ al construirse; sin reconstruir, un cambio
# de codigo no se aplica y se sigue ejecutando la version anterior. Si no hay
# cambios, Docker reutiliza la cache y apenas tarda.
up: _check-env network
> $(DC) up -d --build

down: _check-env
> $(DC_ALL) down

restart: down up

logs: _check-env
> $(DC_ALL) logs -f

ps: _check-env
> $(DC_ALL) ps

# Para la sede y ELIMINA sus volumenes (datos de postgres, lakehouse, checkpoints)
clean: _check-env
> $(DC_ALL) down -v

# Levanta la sede incluyendo su coordinator. Valido en CUALQUIER sede:
# central = primario, chamartin/atocha = respaldo (issue #59).
up-coordinator: _check-env network
> $(DC_ALL) up -d --build

# Para solo el coordinator de la sede; el resto de la sede sigue en pie.
stop-coordinator: _check-env
> $(DC_ALL) stop coordinator

# Consulta el coordinator probando central -> chamartin -> atocha.
# Uso: make failover-check [FAILOVER_PATH=/metrics/daily]
FAILOVER_PATH ?= /health
failover-check:
> $(PYTHON) -m scripts.coordinator_failover $(FAILOVER_PATH)

# Todas las sedes
up-all:
> @for s in $(SITES); do echo ">> up $$s"; $(MAKE) up SITE=$$s; done

up-all-coordinators:
> @for s in $(SITES); do echo ">> up-coordinator $$s"; $(MAKE) up-coordinator SITE=$$s; done

down-all:
> @for s in $(SITES); do echo ">> down $$s"; $(MAKE) down SITE=$$s; done
