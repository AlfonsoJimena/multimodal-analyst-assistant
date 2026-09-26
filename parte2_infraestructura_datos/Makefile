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
#   make up-central-profile SITE=central   # incluye el coordinator (profile central)
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

# Sedes usadas por los targets *-all
SITES := central chamartin atocha

.PHONY: help config build up down restart logs ps clean up-central-profile up-all down-all _check-env

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
> @echo "  make up-central-profile SITE=central - incluye el coordinator (profile central)"
> @echo "  make up-all / make down-all - todas las sedes ($(SITES))"

# Comprueba que existe el .env de la sede antes de actuar
_check-env:
> @test -f $(ENV_FILE) || { echo "ERROR: no existe $(ENV_FILE). SITE='$(SITE)' no es una sede valida ($(SITES))."; exit 1; }

config: _check-env
> $(DC) config

build: _check-env
> $(DC) build

up: _check-env
> $(DC) up -d

down: _check-env
> $(DC) down

restart: down up

logs: _check-env
> $(DC) logs -f

ps: _check-env
> $(DC) ps

# Para la sede y ELIMINA sus volumenes (datos de postgres, lakehouse, checkpoints)
clean: _check-env
> $(DC) down -v

# Levanta la sede incluyendo el coordinator (solo tiene sentido en 'central')
up-central-profile: _check-env
> $(DC) --profile central up -d

# Todas las sedes
up-all:
> @for s in $(SITES); do echo ">> up $$s"; $(MAKE) up SITE=$$s; done

down-all:
> @for s in $(SITES); do echo ">> down $$s"; $(MAKE) down SITE=$$s; done
