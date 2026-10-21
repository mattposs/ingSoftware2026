# Evidencia de la POC — lote `ece83881-91dc-4356-b6cf-eb7ddfa7f759`


### 2.1 Qué hizo cada capa (gold.pipeline_layer_metrics)

```sql
SELECT layer, entity, rows, window_start, window_end, started_at, finished_at FROM gold.pipeline_layer_metrics WHERE _batch_id = :b ORDER BY layer, entity
```

```
     layer              entity  rows              window_start                window_end                       started_at                      finished_at
    bronze       iot_simulator   767 2026-10-19 23:00:00+00:00 2026-10-20 23:00:00+00:00 2026-10-20 23:07:06.205046+00:00 2026-10-20 23:07:06.385443+00:00
    bronze          open_meteo   576 2026-10-12 23:00:00+00:00 2026-10-15 23:00:00+00:00 2026-10-20 23:06:58.015699+00:00 2026-10-20 23:07:06.183069+00:00
      gold daily_field_metrics    48                       NaT                       NaT 2026-10-20 23:07:07.361947+00:00 2026-10-20 23:07:07.677450+00:00
quarantine        measurements    97                       NaT                       NaT 2026-10-20 23:07:06.419124+00:00 2026-10-20 23:07:07.348586+00:00
    silver        measurements  1246                       NaT                       NaT 2026-10-20 23:07:06.419124+00:00 2026-10-20 23:07:07.348586+00:00
```

**Bronze `open_meteo`**: 576 registros · timestamps válidos desde 2026-10-13 00:00:00+00:00 hasta 2026-10-15 23:00:00+00:00 (UTC) · campos: LIT-01, LIT-02, LIT-03, LIT-04, LIT-05, LIT-06, LIT-07, LIT-08

**Bronze `iot_simulator`**: 767 registros · timestamps válidos desde 2026-10-19 23:15:00+00:00 hasta 2026-10-22 23:06:57+00:00 (UTC) · campos: LIT-01, LIT-02, LIT-03, LIT-04, LIT-05, LIT-06, LIT-07, LIT-08, LIT-99
- Intervalo entre lecturas más frecuente: 15 min
- Registros con error inyectado por el simulador: 108 de 767 = 14.08 %

### Errores inyectados por tipo (columna _sim_injected_error)

```
                  tipo  registros
 humidity_out_of_range         15
         bad_timestamp         13
   temperature_extreme         10
     soil_out_of_range         10
            wrong_unit          9
            null_field          9
      future_timestamp          8
negative_precipitation          7
        null_timestamp          7
                 spike          6
         unknown_field          5
                   gap          5
             duplicate          4
```

### 3.1 Métricas de la corrida (gold.dq_run_metrics)

```sql
SELECT _batch_id, status, total, valid, warning, invalid, dq_score, pct_utilizable, run_start, run_end FROM gold.dq_run_metrics WHERE _batch_id = :b
```

```
                           _batch_id status  total  valid  warning  invalid  dq_score  pct_utilizable                        run_start                          run_end
ece83881-91dc-4356-b6cf-eb7ddfa7f759     ok   1343   1193       53       97     88.83           92.78 2026-10-20 23:07:06.036414+00:00 2026-10-20 23:07:07.682368+00:00
```

### 3.2 Hallazgos por regla (gold.dq_errors)

```sql
SELECT rule_id, rule_type, severidad, action, count(*) AS hallazgos FROM gold.dq_errors WHERE _batch_id = :b GROUP BY rule_id, rule_type, severidad, action ORDER BY rule_id, action
```

```
rule_id    rule_type severidad  action  hallazgos
   DQ01  Completitud   Crítica  REJECT          7
   DQ02  Completitud   Crítica  REJECT          9
   DQ03 Consistencia   Crítica  REJECT         21
   DQ04   Integridad   Crítica  REJECT          5
   DQ05     Unicidad   Crítica  REJECT          6
   DQ06 Consistencia   Crítica  REJECT          9
   DQ07      Validez      Alta  REJECT         15
   DQ08      Validez      Alta  REJECT          7
   DQ09      Validez      Alta  REJECT         10
   DQ10      Validez      Alta  REJECT         10
   DQ11  Completitud     Media WARNING        215
   DQ12     Anomalía     Media WARNING         12
```

### 3.3 Hallazgos por severidad

```sql
SELECT severidad, action, count(*) AS hallazgos FROM gold.dq_errors WHERE _batch_id = :b GROUP BY severidad, action ORDER BY severidad, action
```

```
severidad  action  hallazgos
     Alta  REJECT         42
  Crítica  REJECT         57
    Media WARNING        227
```

### 3.4 DQ Score estricto por campo y día (gold.daily_field_metrics.porcentaje_calidad)

```sql
SELECT fecha, field_id, fuente, cantidad_mediciones, porcentaje_calidad FROM gold.daily_field_metrics ORDER BY fuente, field_id, fecha
```

```
     fecha field_id        fuente  cantidad_mediciones  porcentaje_calidad
2026-10-19   LIT-01 iot_simulator                   13               86.67
2026-10-20   LIT-01 iot_simulator                   66               82.19
2026-10-19   LIT-02 iot_simulator                   12               76.92
2026-10-20   LIT-02 iot_simulator                   65               76.06
2026-10-19   LIT-03 iot_simulator                   14               93.33
2026-10-20   LIT-03 iot_simulator                   68               82.19
2026-10-19   LIT-04 iot_simulator                   12               80.00
2026-10-20   LIT-04 iot_simulator                   75               88.46
2026-10-19   LIT-05 iot_simulator                   13               86.67
2026-10-20   LIT-05 iot_simulator                   68               80.00
2026-10-19   LIT-06 iot_simulator                   13               85.71
2026-10-20   LIT-06 iot_simulator                   77               91.46
2026-10-19   LIT-07 iot_simulator                   12               69.23
2026-10-20   LIT-07 iot_simulator                   76               91.14
2026-10-19   LIT-08 iot_simulator                   13               86.67
2026-10-20   LIT-08 iot_simulator                   73               89.87
2026-10-12   LIT-01    open_meteo                    3              100.00
2026-10-13   LIT-01    open_meteo                   24              100.00
2026-10-14   LIT-01    open_meteo                   24              100.00
2026-10-15   LIT-01    open_meteo                   21              100.00
2026-10-12   LIT-02    open_meteo                    3              100.00
2026-10-13   LIT-02    open_meteo                   24              100.00
2026-10-14   LIT-02    open_meteo                   24              100.00
2026-10-15   LIT-02    open_meteo                   21              100.00
2026-10-12   LIT-03    open_meteo                    3              100.00
2026-10-13   LIT-03    open_meteo                   24              100.00
2026-10-14   LIT-03    open_meteo                   24              100.00
2026-10-15   LIT-03    open_meteo                   21              100.00
2026-10-12   LIT-04    open_meteo                    3              100.00
2026-10-13   LIT-04    open_meteo                   24              100.00
2026-10-14   LIT-04    open_meteo                   24              100.00
2026-10-15   LIT-04    open_meteo                   21              100.00
2026-10-12   LIT-05    open_meteo                    3              100.00
2026-10-13   LIT-05    open_meteo                   24              100.00
2026-10-14   LIT-05    open_meteo                   24              100.00
2026-10-15   LIT-05    open_meteo                   21              100.00
2026-10-12   LIT-06    open_meteo                    3              100.00
2026-10-13   LIT-06    open_meteo                   24              100.00
2026-10-14   LIT-06    open_meteo                   24              100.00
2026-10-15   LIT-06    open_meteo                   21              100.00
2026-10-12   LIT-07    open_meteo                    3              100.00
2026-10-13   LIT-07    open_meteo                   24              100.00
2026-10-14   LIT-07    open_meteo                   24              100.00
2026-10-15   LIT-07    open_meteo                   21              100.00
2026-10-12   LIT-08    open_meteo                    3              100.00
2026-10-13   LIT-08    open_meteo                   24              100.00
2026-10-14   LIT-08    open_meteo                   24              100.00
2026-10-15   LIT-08    open_meteo                   21              100.00
```

### 3.5 Misma información como tabla campo × día

```
       fuente field_id  2026-10-12  2026-10-13  2026-10-14  2026-10-15  2026-10-19  2026-10-20
iot_simulator   LIT-01         NaN         NaN         NaN         NaN       86.67       82.19
iot_simulator   LIT-02         NaN         NaN         NaN         NaN       76.92       76.06
iot_simulator   LIT-03         NaN         NaN         NaN         NaN       93.33       82.19
iot_simulator   LIT-04         NaN         NaN         NaN         NaN       80.00       88.46
iot_simulator   LIT-05         NaN         NaN         NaN         NaN       86.67       80.00
iot_simulator   LIT-06         NaN         NaN         NaN         NaN       85.71       91.46
iot_simulator   LIT-07         NaN         NaN         NaN         NaN       69.23       91.14
iot_simulator   LIT-08         NaN         NaN         NaN         NaN       86.67       89.87
   open_meteo   LIT-01       100.0       100.0       100.0       100.0         NaN         NaN
   open_meteo   LIT-02       100.0       100.0       100.0       100.0         NaN         NaN
   open_meteo   LIT-03       100.0       100.0       100.0       100.0         NaN         NaN
   open_meteo   LIT-04       100.0       100.0       100.0       100.0         NaN         NaN
   open_meteo   LIT-05       100.0       100.0       100.0       100.0         NaN         NaN
   open_meteo   LIT-06       100.0       100.0       100.0       100.0         NaN         NaN
   open_meteo   LIT-07       100.0       100.0       100.0       100.0         NaN         NaN
   open_meteo   LIT-08       100.0       100.0       100.0       100.0         NaN         NaN
```

### 4.1 Bronze — un registro tal como llegó (iot_simulator)

```
            columna                                valor
          timestamp                 2026-10-19T23:15:00Z
           field_id                               LIT-01
           latitude                               -32.03
          longitude                               -60.31
        temperature                                15.99
   temperature_unit                                   °C
           humidity                                 69.1
      humidity_unit                                    %
      soil_moisture                                0.281
 soil_moisture_unit                                m³/m³
      precipitation                                  0.0
 precipitation_unit                                   mm
         wind_speed                                  9.8
    wind_speed_unit                                 km/h
             source                        iot_simulator
_sim_injected_error                                 <NA>
          _batch_id ece83881-91dc-4356-b6cf-eb7ddfa7f759
       _ingested_at     2026-10-20 23:07:06.303658+00:00
     _source_system                        iot_simulator
```

### 4.2 Silver — un registro VALID

```
            columna                                valor
          timestamp            2026-10-13 00:00:00+00:00
             source                           open_meteo
           field_id                               LIT-01
           latitude                               -32.03
          longitude                               -60.31
        temperature                                 13.0
           humidity                                 85.0
      soil_moisture                                0.469
      precipitation                                  0.0
         wind_speed                                 10.3
          dq_status                                VALID
       _dq_warnings                                  NaN
_sim_injected_error                                 <NA>
          _batch_id ece83881-91dc-4356-b6cf-eb7ddfa7f759
       _ingested_at     2026-10-20 23:07:06.043389+00:00
     _source_system                           open_meteo
```

### 4.2 Silver — un registro WARNING

```
            columna                                valor
          timestamp            2026-10-20 04:15:00+00:00
             source                        iot_simulator
           field_id                               LIT-01
           latitude                               -32.03
          longitude                               -60.31
        temperature                                 9.56
           humidity                                 85.3
      soil_moisture                                0.281
      precipitation                                  0.0
         wind_speed                                 15.3
          dq_status                              WARNING
       _dq_warnings                                 DQ11
_sim_injected_error                                 <NA>
          _batch_id ece83881-91dc-4356-b6cf-eb7ddfa7f759
       _ingested_at     2026-10-20 23:07:06.303658+00:00
     _source_system                        iot_simulator
```

### 4.3 Quarantine — un registro rechazado

```
            columna                                valor
          timestamp                 2026-10-20T00:15:00Z
           field_id                               LIT-01
           latitude                               -32.03
          longitude                               -60.31
        temperature                                14.34
   temperature_unit                                   °C
           humidity                                 70.9
      humidity_unit                                    %
      soil_moisture                                0.279
 soil_moisture_unit                                m³/m³
      precipitation                                 -3.0
 precipitation_unit                                   mm
         wind_speed                                 10.7
    wind_speed_unit                                 km/h
             source                        iot_simulator
_sim_injected_error               negative_precipitation
          _batch_id ece83881-91dc-4356-b6cf-eb7ddfa7f759
       _ingested_at     2026-10-20 23:07:06.303658+00:00
     _source_system                        iot_simulator
 _rejection_reasons                                 DQ08
       _rejected_at     2026-10-20 23:07:06.761632+00:00
```

### 4.4 Gold — 3 filas de gold.daily_field_metrics

```sql
SELECT fecha, field_id, fuente, temperatura_promedio, precipitacion_total, humedad_suelo_promedio, humedad_ambiental_promedio, cantidad_mediciones, porcentaje_calidad FROM gold.daily_field_metrics ORDER BY fecha DESC, field_id LIMIT 3
```

```
     fecha field_id        fuente  temperatura_promedio  precipitacion_total  humedad_suelo_promedio  humedad_ambiental_promedio  cantidad_mediciones  porcentaje_calidad
2026-10-20   LIT-01 iot_simulator                15.219                  2.9                   0.280                      69.338                   66               82.19
2026-10-20   LIT-02 iot_simulator                16.631                  0.4                   0.292                      68.629                   65               76.06
2026-10-20   LIT-03 iot_simulator                16.923                  0.0                   0.301                      69.684                   68               82.19
```

### 5.0a Rechazos DQ10 que aparecieron solos en la corrida (Quarantine)

```
           timestamp field_id        source  soil_moisture _rejection_reasons _sim_injected_error
2026-10-20T17:15:00Z   LIT-01 iot_simulator           1.35               DQ10   soil_out_of_range
2026-10-20T21:00:00Z   LIT-01 iot_simulator           1.35               DQ10   soil_out_of_range
2026-10-20T09:15:00Z   LIT-02 iot_simulator           1.35               DQ10   soil_out_of_range
2026-10-20T12:00:00Z   LIT-02 iot_simulator           1.35               DQ10   soil_out_of_range
2026-10-20T23:00:00Z   LIT-05 iot_simulator           1.35               DQ10   soil_out_of_range
2026-10-19T23:30:00Z   LIT-06 iot_simulator           1.35               DQ10   soil_out_of_range
2026-10-20T16:00:00Z   LIT-07 iot_simulator           1.35               DQ10   soil_out_of_range
2026-10-20T19:45:00Z   LIT-07 iot_simulator           1.35               DQ10   soil_out_of_range
2026-10-20T07:00:00Z   LIT-08 iot_simulator           1.35               DQ10   soil_out_of_range
2026-10-20T10:15:00Z   LIT-08 iot_simulator           1.35               DQ10   soil_out_of_range
```

### 5.0b Rechazos DQ05 (duplicados) que aparecieron solos en la corrida (Quarantine)

```
           timestamp field_id        source  precipitation _rejection_reasons _sim_injected_error
2026-10-22T23:06:57Z   LIT-01 iot_simulator            0.0          DQ03;DQ05    future_timestamp
2026-10-22T23:06:57Z   LIT-05 iot_simulator            0.0          DQ03;DQ05    future_timestamp
2026-10-20T07:30:00Z   LIT-04 iot_simulator            0.0               DQ05           duplicate
2026-10-20T08:30:00Z   LIT-06 iot_simulator            0.0               DQ05           duplicate
2026-10-20T09:00:00Z   LIT-06 iot_simulator            0.0               DQ05           duplicate
2026-10-20T02:30:00Z   LIT-07 iot_simulator            0.0               DQ05           duplicate
```
