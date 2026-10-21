## Caso A — DQ10: humedad de suelo físicamente imposible en LIT-05 (registro real de la corrida)


#### A.1 Bronze — el registro tal como llegó

```
            columna                                valor
          timestamp                 2026-10-20T23:00:00Z
           field_id                               LIT-05
           latitude                               -33.75
          longitude                               -61.97
        temperature                                19.82
   temperature_unit                                   °C
           humidity                                 65.6
      humidity_unit                                    %
      soil_moisture                                 1.35
 soil_moisture_unit                                m³/m³
      precipitation                                  0.0
 precipitation_unit                                   mm
         wind_speed                                 10.7
    wind_speed_unit                                 km/h
             source                        iot_simulator
_sim_injected_error                    soil_out_of_range
          _batch_id ece83881-91dc-4356-b6cf-eb7ddfa7f759
       _ingested_at     2026-10-20 23:07:06.303658+00:00
     _source_system                        iot_simulator
```

#### A.2 Regla que se dispara (gold.dq_errors)

```sql
SELECT rule_id, rule_type, severidad, action, variable, detalle, measured_at FROM gold.dq_errors WHERE _batch_id = :b AND field_id = 'LIT-05' AND measured_at = :t ORDER BY rule_id
```

```
rule_id rule_type severidad action      variable                       detalle               measured_at
   DQ10   Validez      Alta REJECT soil_moisture fuera del rango físico [0, 1] 2026-10-20 23:00:00+00:00
```

#### A.3 Quarantine — su fila, con el motivo

```
            columna                                valor
          timestamp                 2026-10-20T23:00:00Z
           field_id                               LIT-05
           latitude                               -33.75
          longitude                               -61.97
        temperature                                19.82
   temperature_unit                                   °C
           humidity                                 65.6
      humidity_unit                                    %
      soil_moisture                                 1.35
 soil_moisture_unit                                m³/m³
      precipitation                                  0.0
 precipitation_unit                                   mm
         wind_speed                                 10.7
    wind_speed_unit                                 km/h
             source                        iot_simulator
_sim_injected_error                    soil_out_of_range
          _batch_id ece83881-91dc-4356-b6cf-eb7ddfa7f759
       _ingested_at     2026-10-20 23:07:06.303658+00:00
     _source_system                        iot_simulator
 _rejection_reasons                                 DQ10
       _rejected_at     2026-10-20 23:07:06.761632+00:00
```

#### A.4 Gold — la fila del día de ese registro

El registro es del 2026-10-20 23:00:00+00:00 UTC, que en hora local es el día 2026-10-20.

```sql
SELECT fecha, field_id, fuente, cantidad_mediciones, humedad_suelo_promedio, porcentaje_calidad, _batch_id FROM gold.daily_field_metrics WHERE field_id = 'LIT-05' AND fuente = 'iot_simulator' AND fecha = :f
```

```
     fecha field_id        fuente  cantidad_mediciones  humedad_suelo_promedio  porcentaje_calidad                            _batch_id
2026-10-20   LIT-05 iot_simulator                   68                   0.316                80.0 ece83881-91dc-4356-b6cf-eb7ddfa7f759
```

**Comprobación de que NO llegó a Gold:**

- Registros de Silver con la misma identidad (iot_simulator, LIT-05, 2026-10-20 23:00:00+00:00): **0**.
- Registros de Silver de LIT-05 / iot_simulator del día 2026-10-20: **68**; `cantidad_mediciones` en Gold: **68**.
- Humedad de suelo promedio en Gold: **0.316** m³/m³ (calculada solo con Silver: 0.316). El valor rechazado (1,35) no está incluido.
- Máxima humedad de suelo entre los registros que alimentan esa fila de Gold: **0.321** m³/m³.

## Caso B — DQ05: precipitación duplicada en LIT-02 (inyección controlada)

En la corrida no hubo duplicados en LIT-02. Para provocarlo se toma la lectura real de LIT-02 con más lluvia (precipitación 2.6 mm, 2026-10-20 00:00:00+00:00 UTC) y se la vuelve a enviar idéntica, en un lote nuevo, por el código real del pipeline (`run_silver` y `run_gold`), como si el sensor la hubiera transmitido dos veces. La columna `_sim_injected_error` la marca como `poc_duplicado_controlado`.


#### B.0 La lectura original, ya procesada en la corrida principal (Bronze)

```
            columna                                valor
          timestamp                 2026-10-20T00:00:00Z
           field_id                               LIT-02
           latitude                               -33.01
          longitude                               -58.52
        temperature                                 15.8
   temperature_unit                                   °C
           humidity                                 69.2
      humidity_unit                                    %
      soil_moisture                                0.289
 soil_moisture_unit                                m³/m³
      precipitation                                  2.6
 precipitation_unit                                   mm
         wind_speed                                 14.1
    wind_speed_unit                                 km/h
             source                        iot_simulator
_sim_injected_error                                 <NA>
          _batch_id ece83881-91dc-4356-b6cf-eb7ddfa7f759
       _ingested_at     2026-10-20 23:07:06.303658+00:00
     _source_system                        iot_simulator
```

#### B.0b Estado del lote ANTES de recuperarlo (quedó a medio procesar por el bug de las trazas)

La primera vez que se envió el duplicado, el pipeline falló al guardar las trazas (bug corregido en `src/metrics/trace.py`). Bronze ya estaba escrito, así que el lote se recupera reprocesándolo desde Bronze con el código corregido, sin volver a enviar el dato.

```sql
SELECT _batch_id, status, total, valid, warning, invalid, dq_score, run_end FROM gold.dq_run_metrics WHERE _batch_id = :b
```

```
        _batch_id  status  total  valid  warning  invalid  dq_score run_end
poc-dq05-ba8db9eb running      1      0        0        1       0.0    None
```
[SILVER] Lote vacío para agro/measurements: no se escribe archivo.
[QUARANTINE] 1 registros -> C:\Users\Matt_Poss\OneDrive\Facultad\2026\Segundo cuatrimestre\INGENIERÍA DE SOFTWARE\TPO\IngSoftwareETL-1\storage\poc\quarantine\agro\measurements\year=2026\month=10\rejected_poc-dq05-ba8db9eb.parquet
[DQ] total=1 valid=0 warning=0 invalid=1 score=0.0% utilizable=0.0% errores=1
[DB] Upsert de 8 filas en gold.fields.
[DB] Lote vacío: se omite upsert en gold.daily_field_metrics.

#### B.1 Bronze — el duplicado tal como llegó (lote nuevo)

```
            columna                            valor
          timestamp             2026-10-20T00:00:00Z
           field_id                           LIT-02
           latitude                           -33.01
          longitude                           -58.52
        temperature                             15.8
   temperature_unit                               °C
           humidity                             69.2
      humidity_unit                                %
      soil_moisture                            0.289
 soil_moisture_unit                            m³/m³
      precipitation                              2.6
 precipitation_unit                               mm
         wind_speed                             14.1
    wind_speed_unit                             km/h
             source                    iot_simulator
_sim_injected_error         poc_duplicado_controlado
          _batch_id                poc-dq05-ba8db9eb
       _ingested_at 2026-10-20 23:08:38.344988+00:00
     _source_system                    iot_simulator
```

#### B.2 Regla que se dispara (gold.dq_errors)

```sql
SELECT rule_id, severidad, action, field_id, measured_at, detalle FROM gold.dq_errors WHERE _batch_id = :b
```

```
rule_id severidad action field_id               measured_at                                   detalle
   DQ05   Crítica REJECT   LIT-02 2026-10-20 00:00:00+00:00 registro ya procesado en un lote anterior
```

#### B.3 Quarantine — su fila, con el motivo

```
            columna                            valor
          timestamp             2026-10-20T00:00:00Z
           field_id                           LIT-02
           latitude                           -33.01
          longitude                           -58.52
        temperature                             15.8
   temperature_unit                               °C
           humidity                             69.2
      humidity_unit                                %
      soil_moisture                            0.289
 soil_moisture_unit                            m³/m³
      precipitation                              2.6
 precipitation_unit                               mm
         wind_speed                             14.1
    wind_speed_unit                             km/h
             source                    iot_simulator
_sim_injected_error         poc_duplicado_controlado
          _batch_id                poc-dq05-ba8db9eb
       _ingested_at 2026-10-20 23:08:38.344988+00:00
     _source_system                    iot_simulator
 _rejection_reasons                             DQ05
       _rejected_at 2026-10-20 23:10:12.560515+00:00
```

#### B.4 Resumen del lote de la inyección (gold.dq_run_metrics)

```sql
SELECT _batch_id, status, total, valid, warning, invalid, dq_score FROM gold.dq_run_metrics WHERE _batch_id = :b
```

```
        _batch_id status  total  valid  warning  invalid  dq_score
poc-dq05-ba8db9eb     ok      1      0        0        1       0.0
```

#### B.5 Gold — la fila del día ANTES de procesar el duplicado (el intento fallido no llegó a escribir en Gold)

```sql
SELECT fecha, field_id, fuente, precipitacion_total, cantidad_mediciones, porcentaje_calidad, _batch_id FROM gold.daily_field_metrics WHERE field_id = 'LIT-02' AND fuente = 'iot_simulator' AND fecha = :f
```

```
     fecha field_id        fuente  precipitacion_total  cantidad_mediciones  porcentaje_calidad                            _batch_id
2026-10-19   LIT-02 iot_simulator                  2.6                   12               76.92 ece83881-91dc-4356-b6cf-eb7ddfa7f759
```

#### B.6 Gold — la misma fila DESPUÉS de procesarlo

```
     fecha field_id        fuente  precipitacion_total  cantidad_mediciones  porcentaje_calidad                            _batch_id
2026-10-19   LIT-02 iot_simulator                  2.6                   12               76.92 ece83881-91dc-4356-b6cf-eb7ddfa7f759
```

#### B.7 ¿El lote del duplicado escribió algo en Gold?

```sql
SELECT count(*) AS filas_de_gold_escritas_por_el_lote FROM gold.daily_field_metrics WHERE _batch_id = :b
```

```
 filas_de_gold_escritas_por_el_lote
                                  0
```

**Comprobación de que la precipitación NO se duplicó:**

- Copias de la lectura (2026-10-20 00:00:00+00:00 UTC) en Silver: **1**.
- La lectura es del 2026-10-20 00:00 UTC = 2026-10-19 21:00 hora local, por eso cae en la fila del 2026-10-19.
- Suma de precipitación de Silver para LIT-02 el 2026-10-19: **2.6** mm; `precipitacion_total` en Gold: **2.6** mm (antes: 2.6 mm).

Lote de la inyección: `poc-dq05-ba8db9eb`
