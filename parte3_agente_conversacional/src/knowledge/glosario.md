# Glosario del dominio

Base de conocimiento del agente: qué significan los datos que devuelven las
herramientas y qué preguntas se pueden (y no se pueden) responder.
Revisado contra `schema.py`, `cleaning.py` y `gold.py` de la parte 2 y
contra el diccionario de datos de la TLC (yellow taxis, 18/03/2025).

## Origen de los datos

- Viajes de **taxis amarillos de Nueva York** (dataset público de la NYC
  Taxi & Limousine Commission, TLC). La muestra de la parte 2 son 999 viajes.
- Los viajes están repartidos en **tres sedes** de la empresa. Cada sede
  guarda sus datos; el agente solo recibe **agregados** (conteos y sumas)
  a través del coordinador.

## Sedes

| Sede | `site_id` | Viajes que guarda |
|---|---|---|
| Central | `central` | `PULocationID % 3 == 0` |
| Chamartín | `chamartin` | `PULocationID % 3 == 1` |
| Atocha | `atocha` | `PULocationID % 3 == 2` |

- El reparto es **técnico, no geográfico**: Chamartín y Atocha no tienen
  nada que ver con las zonas de Nueva York de sus viajes.
- Cada zona de recogida pertenece a **una sola sede**.
- Si una sede no responde, el resultado es **parcial**: incluye solo las
  sedes de `sites_ok` y hay que decir cuáles faltan (`sites_failed`).

## Métricas

| Métrica | Cálculo | Unidad |
|---|---|---|
| `trips` | número de viajes (`trip_count`) | viajes |
| `revenue` | suma de `total_amount`: lo cobrado al pasajero (tarifa, extras, impuestos, peajes, recargos y propinas con tarjeta) | dólares |
| `avg_fare` | Σ `fare_amount` / Σ viajes (tarifa del taxímetro) | dólares |
| `avg_distance` | Σ `trip_distance` / Σ viajes | millas |
| `avg_tip` | Σ `tip_amount` / Σ viajes | dólares |
| `avg_total` | Σ `total_amount` / Σ viajes | dólares |

- Las medias se calculan **siempre** como Σ sumas / Σ conteos después de
  combinar sedes o días, **nunca** como media de las medias.
- **Propinas:** solo incluyen las pagadas con tarjeta; las propinas en
  efectivo no se registran (TLC). Por eso `avg_tip` es bajo en los viajes
  pagados en efectivo.
- Moneda: dólares estadounidenses. Distancias: millas.

## Métodos de pago (`payment_type`)

| Código | Nombre | Original TLC |
|---|---|---|
| 0 | tarifa Flex Fare | Flex Fare trip |
| 1 | tarjeta | Credit card |
| 2 | efectivo | Cash |
| 3 | sin cargo | No charge |
| 4 | disputa | Dispute |
| 5 | desconocido | Unknown |
| 6 | anulado | Voided trip |

El mapa del código está en `src/knowledge/payment_types.py`. La muestra solo
tiene los códigos 1 a 4.

## Qué viajes cuentan

Las cifras salen de la capa Gold de cada sede, que solo incluye viajes
válidos:

- **Se excluyen los viajes en cuarentena** (datos no fiables): fechas que
  faltan, llegada anterior o igual a la salida, duración de más de 180
  minutos, distancia negativa, más de 9 pasajeros o importes negativos sin
  explicación.
- **Se excluyen las cancelaciones:** viajes con algún **importe negativo**
  y pago "sin cargo" (3) o "disputa" (4).
- Un viaje con pago 3 o 4 **sin importes negativos sí cuenta**.
- Los viajes con 0 pasajeros sí cuentan.
- Los duplicados (mismo `trip_id`) se cuentan una sola vez.

## Tablas y fechas

| Tabla | Agrupa por | ¿Tiene fechas? |
|---|---|---|
| horaria | hora de recogida (`trip_hour`) | sí |
| diaria | día de recogida (`trip_date`) | sí |
| zonas | zona de recogida (`pu_location_id`) | **no**: acumulado de todo el periodo |
| pagos | método de pago (`payment_type`) | **no**: acumulado de todo el periodo |

- Zonas y pagos **no sirven** para preguntas sobre un día concreto ("¿y ayer?").
- **Fechas con datos:**
  - **histórico** (80 % más antiguo de cada sede): viajes del 31/12/2019 por
    la noche y del 01/01/2020;
  - **tiempo real** (20 % más reciente): sus horas se desplazan a la fecha y
    hora en que se arrancó el simulador, así que aparecen con la fecha de
    la demo.
- Entre las dos tandas no hay datos: antes de responder sobre un periodo,
  consultar qué fechas tienen datos (`get_platform_status`).

## Zonas

- Las 265 zonas de taxi de la TLC (`src/knowledge/taxi_zone_lookup.csv`):
  ID, nombre (`Zone`), distrito (`Borough`) y tipo de zona.
- Distritos: Manhattan, Brooklyn, Queens, Bronx, Staten Island y EWR
  (aeropuerto de Newark). El 264 es "Unknown" y el 265, "Outside of NYC".
- La zona es la de **recogida** (`PULocationID`). La zona de destino no
  está en los agregados.

## Qué no hay (y no se puede responder)

- **Viajes individuales**, conductores, pasajeros o vehículos: solo existen
  agregados. La alternativa es dar las métricas de la zona o de la hora.
- **Celdas pequeñas:** una zona o un método de pago con menos de 5 viajes
  no se muestra (privacidad).
- Origen-destino, rutas, matrículas o datos de otras ciudades.
- Datos de fechas fuera de las que tienen datos (ver "Tablas y fechas").
