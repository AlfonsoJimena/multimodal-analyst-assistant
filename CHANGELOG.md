# Changelog

Todos los cambios notables del proyecto **multimodal-analyst-assistant** se documentan en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y este proyecto se adhiere al [Versionado Semántico](https://semver.org/lang/es/).

## [1.0.1] - 2026-10-06

### Fixed
- Parte 1: el demo multimodelo usa el MLP reentrenado con normalización L0 y se actualiza el README de modelos (#139).

## [1.0.0] - 2026-10-05

Versión final de entrega del proyecto.

### Removed
- Carpetas vacías `docs/decisiones/`, `docs/memoria/` y `docs/presentacion/` (sus `.gitkeep`).

## [1.0.0-beta.2] - 2026-10-05

### Added
- Scripts de arranque y parada de todo el proyecto (#136).

### Changed
- README raíz reescrito para que el proyecto sea reproducible de principio a fin y revisión de los READMEs de las partes 2 y 3 (#137).

### Fixed
- Parte 1: reentrenado el MLP con normalización L0 (#135).

## [1.0.0-beta.1] - 2026-10-05

Primera versión con las tres partes del proyecto integradas.

### Added
- Parte 3: esqueleto y contratos compartidos del agente (#116).
- Parte 3: capa de datos con failover, agregación y privacidad.
- Parte 3: base de conocimiento de zonas, pagos y glosario (#120).
- Parte 3: herramientas `get_kpis`, `compare_sites` y `get_timeseries` (#121), y herramientas de pagos, zonas y estado de la plataforma.
- Parte 3: pasarela LLM con fallback y selección de modelos gratuitos.
- Parte 3: orquestador del diálogo con bucle de tool calling y CLI `python -m src.agent` para probar el agente con el LLM real.
- Parte 3: prompt de sistema con reglas, glosario y fecha del día.
- Parte 3: interfaz de chat en Streamlit contra la API del agente, con bloques, avisos, trazabilidad y estado.
- Parte 3: Docker, compose, Makefile y CI del chatbot.
- Parte 3: tests de integración reales con la parte 2 y escenarios de fallo (#130).
- Parte 3: framework de evaluación de calidad del modelo del chatbot y evaluación completa (#131).
- Parte 3: documentación de entrega (#133).
- Parte 2: desglose por sede en el coordinador con `breakdown=site` (#117).
- Parte 2: coordinador mock con fixtures deterministas (#118).

### Changed
- Parte 1: reentrenada la CNN con normalización L0 y documentados los modelos (#134).

### Removed
- Parte 1: retirado el modelo LSTM (#134).

## [0.4.0] - 2026-10-01

Requisitos mínimos de la parte 2: infraestructura de datos distribuida.

### Added
- Estructura de la parte 2 y actualización del README (#45, #71).
- Esquema de datos (`schema.py`), preparación de datos, producer y documentación del esquema (#72, #73, #74, #75).
- Compose central con monitorización (#76).
- Spark: reglas de calidad de datos compartidas (`cleaning.py`) (#77).
- Spark: ingesta batch y streaming a Bronze (#78).
- Spark: capa Silver con separación de cuarentena (#79).
- Spark: agregados de negocio en Gold (#80) y upsert en Postgres (#81).
- Plantillas SQL de tablas Gold y de datos en cuarentena o con errores (#82).
- `.gitattributes` para normalizar finales de línea (#82).
- Configuración inicial del coordinador (#83).
- `docker-compose.site.yml` parametrizado por sede, `.env` por sede (central, chamartin, atocha) y Makefile de despliegue por sede (#85, #86, #87).
- Replicación del coordinador (#89).
- Tests de disponibilidad con sedes caídas y failover del coordinador (M1) (#91).
- Tests de transferencia de datos crudos fuera de cada sede (M2) (#93).
- Tests de exactitud federada frente a cálculo centralizado (M3) (#95).
- Comparativa de alternativas y adaptación a E3/E4/E8 (#96).
- README final de la parte 2 con instrucciones de ejecución y actualización de la arquitectura (#97).

### Fixed
- Timeout del cliente mayor que el del coordinador con las sedes (#90).
- Imagen base de Spark fijada a Debian bookworm para mantener OpenJDK 17 (#92).
- Carga del histórico en el despliegue y separación de Bronze batch/streaming (#94).
- Métrica de negocio `trips_processed_total` y acceso de Prometheus al host (#98).

## [0.3.0] - 2026-09-21

Requisitos mínimos de la parte 1: reconocimiento de gestos.

### Added
- Fusión del repositorio de la parte 1 en el proyecto (#23).
- Notebook, modelos entrenados y script de fusión del dataset (#39).
- Modelo MLP y sus notebooks (#40).
- Notebook con métricas y modelo LSTM entrenado (#42).
- Evaluación del modelo SVM sobre el dataset del equipo (#43).

### Changed
- Gestos renombrados en `record_dataset` (#33).
- Archivos del modelo Random Forest reubicados (#41).
- Directorio actualizado en el README (#24).

### Fixed
- Uso de la webcam en lugar de la cámara de la Raspberry (#26).
- Bug en el tratamiento de color RGB (#28).
- Funcionamiento de la cámara (#30).

## [0.2.0] - 2026-09-09

Estructura inicial del proyecto lista para empezar a trabajar.

### Added
- README con el contexto del proyecto (#4).
- `CHANGELOG.md` (#7, #19).
- Estructura de carpetas del proyecto (#8).

### Changed
- Carpeta `.github` unificada con las plantillas de GitHub (#10).
- Plantilla de issues migrada al formato de carpeta (#14).

### Fixed
- `CODEOWNERS` (#16).
- Directorio en el README (#17).

## [0.1.0] - 2026-09-07

Configuración mínima para colaborar en el repositorio.

### Added
- Carpeta `.github` con `CODEOWNERS`, plantilla de issues y plantilla de pull requests (#3).
- `CONTRIBUTING.md` con la guía para contribuidores: convención de nombres de ramas, Conventional Commits y reglas para pull requests (#3).
