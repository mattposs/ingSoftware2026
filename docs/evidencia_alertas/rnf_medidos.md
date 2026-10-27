# Requerimientos no funcionales medidos

Generado por `scripts/verify_rnf.py` el 26/10/2026 20:48 (hora local). Entorno leído: **STAGING** (solo lectura). Las pruebas que escriben (RNF10, RNF03 y RNF06) corrieron en una base aislada (`agro_rnf`) con un lake temporal.

| RNF | Qué se midió | Valor medido | Objetivo | Resultado |
|---|---|---|---|---|
| RNF07 | Corridas por día en gold.dq_run_metrics | Últimos días: 2026-10-05: 12, 2026-10-06: 9, 2026-10-13: 11, 2026-10-14: 1, 2026-10-19: 41, 2026-10-20: 8, 2026-10-26: 8 | 96 por día (una cada 15 min) | **No cumple** |
| RNF08 | Frescura: finished_at − last_measured_at | p95 = 6.14 min · máximo = 6.8 min (4 corridas) | p95 ≤ 20 min y máximo ≤ 30 min | Cumple |
| RNF09 | duration_seconds de las corridas incrementales | p95 = 36.39 s · máximo = 38.36 s (4 corridas) | ≤ 2 min (120 s) | Cumple |
| RNF10 | Reproceso completo de un día simulado (200 sensores × 96) | 7.65 s para 19.355 registros de Bronze (19.200 lecturas + duplicados inyectados) | ≤ 5 min (300 s) | Cumple |
| RNF02 | Registros de Bronze con _batch_id, _ingested_at o _source_system nulos | 0 de 10.692 filas (94 archivos) | 0 | Cumple |
| RNF03 | Reprocesar un día desde Bronze y comparar gold.daily_field_metrics | 508 filas antes y 508 después; idénticas; 0 claves duplicadas | Idéntico, sin duplicados | Cumple |
| RNF04 | Registros INVALID en Gold | 0 INVALID en Silver (única fuente de Gold. 10.007 filas); 0 de 289 filas de Gold no cuadran con Silver | 0 | Cumple |
| RNF06 | Cambiar un umbral en config/rules.yaml sin tocar código | DQ09 warning máx. 45 °C → 0 warnings; con 25 °C → 44 warnings (mismo lote, temp. máx. 26.99 °C). Archivo restaurado: sí | La corrida aplica el umbral nuevo | Cumple |

## Cómo se midió y qué tener en cuenta

- **Corridas leídas:** 90 en `gold.dq_run_metrics`; 7 tienen las columnas de monitoreo (4 SUCCESS, 3 FAILED), desde 2026-10-26 23:00:20.180892+00:00. RNF08 y RNF09 solo pueden medirse sobre esas corridas; las anteriores tienen las columnas en NULL.
- **RNF07** cuenta las filas por día calendario (hora Argentina). Solo se evalúan los días completos: el de hoy está en curso. El scheduler corre en Docker en una computadora personal: si la máquina estuvo apagada o suspendida, ese día tiene menos corridas. Además, una corrida sin datos nuevos no deja fila.
- **RNF08** se mide sobre las corridas SUCCESS. last_measured_at sale de Silver: es el timestamp máximo de los registros válidos del lote.
- **RNF10** usa una copia de `config/` con un `field_id` por sensor (200, por ejemplo `LIT-01-S01`), porque el pipeline identifica las lecturas por campo. Las lecturas las genera el simulador IoT con su tasa de error normal: los 8 campos reales, una vez por número de sensor y con otra semilla, para conservar el perfil climático de cada campo. El tiempo es el de `reprocess()` (Silver + Gold) leyendo desde Bronze, en esta computadora.
- **RNF04**: Gold no guarda el estado de cada registro, porque se calcula solo con Silver. Se mide que Silver no tenga INVALID y que la cantidad de mediciones de cada fila de Gold coincida con Silver.
- **RNF06** modifica `config/rules.yaml` (warning de DQ09, de 45 °C a 25 °C), corre el mismo lote en un proceso nuevo y lo restaura; se comprueba con el hash SHA-256 que el archivo quedó igual que antes.
