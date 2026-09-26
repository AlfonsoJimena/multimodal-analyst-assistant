# M1 · Disponibilidad con sedes caídas

20 consultas por escenario, repartidas entre /metrics/hourly, /daily, /zone y /payment, lanzadas con el cliente de failover (central → chamartín → atocha).

| Escenario | Sedes sin API | Coordinadores caídos | Disponibilidad | Completas | Marcado correcto | Responde | p50 (ms) | p95 (ms) |
|---|---|---|---|---|---|---|---|---|
| Las tres sedes en pie | — | — | 100% | 100% | 100% | central | 51 | 72 |
| site_api de Central parada | central | — | 100% | 0% | 100% | central | 49 | 62 |
| site_api de Chamartín parada | chamartin | — | 100% | 0% | 100% | central | 43 | 52 |
| site_api de Atocha parada | atocha | — | 100% | 0% | 100% | central | 43 | 46 |
| site_api de Atocha congelada (docker pause) | atocha | — | 100% | 0% | 100% | central | 5063 | 5073 |
| Central entera (API + coordinador primario) | central | central | 100% | 0% | 100% | chamartin | 51 | 66 |
| Chamartín y Atocha enteras | atocha, chamartin | atocha, chamartin | 100% | 0% | 100% | central | 45 | 61 |
| Central y Chamartín enteras | central, chamartin | central, chamartin | 100% | 0% | 100% | atocha | 57 | 69 |
| Las tres sedes caídas | atocha, central, chamartin | atocha, central, chamartin | 0% | 0% | 0% | — | 20 | 26 |
