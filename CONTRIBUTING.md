# Contribuir a este repositorio

Guía rápida para que todo el equipo trabaje de forma coherente y sin pisarse el trabajo.

## Flujo de trabajo general

1. Todo el trabajo pasa por **Issues** y **Pull Requests**. Nadie sube código directo a `main` (está protegida).
2. Antes de empezar una tarea, abre (o coge) una Issue que la describa.
3. Asígnate la Issue si vas a trabajar en ella, para que el resto sepa que está cogida.
4. Crea una rama a partir de `main` para esa tarea.
5. Cuando termines, abre un Pull Request hacia `main` y pide revisión.
6. Una vez aprobado, se mergea y se cierra la Issue automáticamente (si el PR usa `Closes #<número>`).

## Nomenclatura de ramas

- `feature/nombre-corto` — nueva funcionalidad
- `fix/nombre-corto` — corrección de un bug
- `docs/nombre-corto` — documentación
- `chore/nombre-corto` — mantenimiento (configuración, dependencias, etc.)

Ejemplos: `feature/login-usuario`, `fix/error-calculo-notas`

## Commits

Usamos un formato tipo *Conventional Commits*:

```
tipo(ámbito opcional): descripción breve en presente
```

### Tipos permitidos

* `feat`: nueva funcionalidad para el usuario
* `fix`: corrección de un error
* `chore`: mantenimiento, configuración, tareas que no afectan al código fuente ni a los tests
* `docs`: cambios en documentación
* `refactor`: cambio de código que no corrige un bug ni añade una funcionalidad
* `test`: añadir o modificar tests
* `style`: cambios de formato (espacios, indentación) sin afectar la lógica
* `perf`: cambios que mejoran el rendimiento
* `build`: cambios que afectan al sistema de build o a dependencias externas (ej. `requirements.txt`, `setup.py`)
* `ci`: cambios en archivos y scripts de integración continua (ej. workflows de GitHub Actions)
* `revert`: revierte un commit anterior

### Ámbito (scope)

El ámbito entre paréntesis es opcional y sirve para acotar a qué parte del proyecto afecta el cambio (ej. `fix(softmax)`, `refactor(embeddings)`).

### Seguridad

Para issues o commits relacionados con seguridad (por ejemplo, vulnerabilidades en dependencias), usa el tipo `fix` con el ámbito `security`:

```
fix(security): actualizar numpy por vulnerabilidad CVE-XXXX
```

### Ejemplos

```
feat: añadir entrenamiento skip-gram con negative sampling
fix(softmax): corregir desbordamiento numérico en la exponencial
chore: configurar protección de rama main y convenciones de repositorio
docs: documentar uso de la clase Word2Vec en el README
refactor(embeddings): simplificar inicialización de matrices de pesos
test: añadir tests para la función de similitud coseno
build: actualizar numpy a la versión 2.0
ci: añadir workflow de GitHub Actions para ejecutar tests
fix(security): actualizar dependencia con vulnerabilidad conocida
```

## Issues

- Usa la plantilla al abrir una Issue nueva.
- Usa etiquetas (labels) para clasificar: `bug`, `feature`, `documentation`, `question`...
- Sé específico en el título; evita títulos genéricos como "arreglar cosas".

## Pull Requests

- Usa la plantilla de PR.
- Vincula la Issue correspondiente (`Closes #12`).
- Descripción clara de qué cambia y por qué.
- Al menos **1 aprobación** de otro miembro del equipo antes de mergear (según la protección de `main`).
- Resuelve los comentarios de revisión antes de mergear.
- Se recomienda usar "Squash and merge" para mantener el historial de `main` limpio y legible.

## Revisión de código

- Sé constructivo: el objetivo es aprender y mejorar el trabajo conjunto, no señalar errores.
- Si algo no se entiende, pregunta directamente en el PR.
- No hace falta ser exhaustivo: revisa que el código haga lo que dice, que no rompa nada obvio y que sea legible.

## Dudas

Si algo no está claro, pregúntalo al equipo antes de bloquearte trabajando en solitario.
