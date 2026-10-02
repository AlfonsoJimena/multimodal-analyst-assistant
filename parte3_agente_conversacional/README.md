# Parte 3 · Agente conversacional

Chatbot que responde preguntas en lenguaje natural sobre los datos de la
parte 2. Arquitectura y contratos en [`ARQUITECTURA.md`](ARQUITECTURA.md).

## Estructura

```
src/api/        contrato de /chat (schemas.py) y la API (main.py)
src/agent/      config, pasarela LLM, orquestador y prompt
src/tools/      formato/registro de herramientas (base.py) y herramientas
src/data/       cliente del coordinador, agregacion y privacidad
src/knowledge/  zonas de NYC, glosario y tipos de pago
src/ui/         interfaz Streamlit
mock/           coordinador falso para desarrollar sin la parte 2
tests/          tests unitarios (sin red) y de integracion (--integration)
```

## Puesta en marcha (desarrollo)

```bash
cd parte3_agente_conversacional
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # y rellena OPENROUTER_API_KEY
```

## Coordinador mock

Para desarrollar y probar el chatbot sin levantar la parte 2 (que ocupa
8-9 GB), `mock/` incluye un coordinador falso con el mismo contrato que el
real (incluido `breakdown=site`), servido desde fixtures deterministas.

```bash
# Desde parte3_agente_conversacional/
uvicorn mock.mock_coordinator:app --port 8190
```

Luego apunta `COORDINATOR_URLS=http://localhost:8190` en tu `.env`.

Fallos simulados con variables de entorno:

```bash
DOWN_SITES=atocha uvicorn mock.mock_coordinator:app --port 8190   # sede caida
SLOW_SITES=atocha SLOW_SECONDS=6 uvicorn mock.mock_coordinator:app --port 8190  # sede lenta
```

Regenerar las fixtures (deterministas, salen idénticas):

```bash
python -m mock.generar_fixtures
```

## Tests

```bash
# Desde parte3_agente_conversacional/
pytest                 # unitarios, sin red ni Docker
pytest --integration   # ademas, contra el coordinador real o el LLM
```

## Estado

En construccion por issues (ver etiqueta `parte3`). Bloque 1 (cimientos y
datos) → bloque 2 (herramientas) → bloque 3 (agente) → bloque 4 (interfaz y
despliegue) → bloque 5 (calidad y entrega).
