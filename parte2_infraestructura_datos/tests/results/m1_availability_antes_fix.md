# M1 · Disponibilidad con sedes caídas

20 consultas por escenario, repartidas entre /metrics/hourly, /daily, /zone y /payment, lanzadas con el cliente de failover (central → chamartín → atocha).

| Escenario | Sedes sin API | Coordinadores caídos | Disponibilidad | Completas | Marcado correcto | Responde | p50 (ms) | p95 (ms) |
|---|---|---|---|---|---|---|---|---|
| Las tres sedes en pie | — | — | 100% | 100% | 100% | central | 43 | 50 |
| site_api de Central parada | central | — | 100% | 0% | 100% | central | 69 | 118 |
| site_api de Chamartín parada | chamartin | — | 100% | 0% | 100% | central | 43 | 50 |
| site_api de Atocha parada | atocha | — | 100% | 0% | 100% | central | 43 | 51 |
| site_api de Atocha congelada (docker pause) | atocha | — | 0% | 0% | 0% | — | 15092 | 15106 |
| Central entera (API + coordinador primario) | central | central | 100% | 0% | 100% | chamartin | 51 | 57 |
| Chamartín y Atocha enteras | atocha, chamartin | atocha, chamartin | 100% | 0% | 100% | central | 43 | 55 |
| Central y Chamartín enteras | central, chamartin | central, chamartin | 100% | 0% | 100% | atocha | 57 | 135 |
| Las tres sedes caídas | atocha, central, chamartin | atocha, central, chamartin | 0% | 0% | 0% | — | 21 | 28 |
