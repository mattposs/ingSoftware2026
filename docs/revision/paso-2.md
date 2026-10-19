# Revisión del paso 2: tasa de error simulada

## 1. Qué pediste vs. qué hiciste

| Ítem de la especificación | Qué hice |
|---|---|
| `config/pipeline.yaml`: `error_rate = 0.14` | Hecho. Pasó de `0.08` a `0.14`. Medido con el simulador real: 215 de 1539 registros con error = 14,0 %. |
| Distribución objetivo: suelo faltante o fuera de rango 6 %, precipitación duplicada 3 %, huecos 3 %, otros 2 % | **No se puede con el simulador actual.** Medí la distribución real (sección 3) y propongo un cambio (sección 5). No lo implementé. |
| "Si el simulador no permite esa distribución, decímelo en el informe" | Está en la sección 5. |
| Registrar decisiones en `docs/decisiones.md` | Agregada D21. |

Además actualicé dos comentarios que decían "~8 %" (`config/pipeline.yaml` y el docstring de `src/ingestion/iot_simulator.py`).

## 2. Archivos cambiados y hash del commit

Un commit no puede contener su propio hash; el hash se informa en el chat y se ve con `git log --oneline -3`. Commit padre: `80c852e`.

- `config/pipeline.yaml`
- `src/ingestion/iot_simulator.py` (solo el docstring)
- `docs/decisiones.md` (D21)
- `docs/revision/paso-2.md` (este archivo)

## 3. Comandos que corrí y su salida real

Distribución real de errores del simulador con `error_rate` 0,14 (script que llama a `iot_simulator.generate` con 48 h de datos y semilla 7, `APP_ENV=prod` para usar la configuración base):

```
error_rate efectivo: 0.14
registros 1539 con error 215 (14.0%)
  bad_timestamp             23  1.49% de los registros
  null_field                22  1.43% de los registros
  wrong_unit                21  1.36% de los registros
  future_timestamp          19  1.23% de los registros
  humidity_out_of_range     19  1.23% de los registros
  negative_precipitation    18  1.17% de los registros
  temperature_extreme       18  1.17% de los registros
  null_timestamp            17  1.10% de los registros
  duplicate                 14  0.91% de los registros
  unknown_field             13  0.84% de los registros
  spike                     12  0.78% de los registros
  gap                       11  0.71% de los registros
  soil_out_of_range          8  0.52% de los registros
suelo faltante/fuera de rango (objetivo 6%): 0.52%
precipitación duplicada (objetivo 3%): 0.91%
huecos (objetivo 3%): 0.71%
otros (objetivo 2%): 6.37%
```

(Una sola muestra con una semilla; los porcentajes varían un poco entre corridas, pero el reparto parejo entre los 13 tipos se ve claro.)

`ruff check .`:

```
All checks passed!
```

`python -m src.validation.check_rules`:

```
[RULES] OK: 12 reglas y 8 campos válidos.
```

`python -m pytest -q -rs` (suite completa, sin base de datos):

```
86 passed, 4 skipped in 14.40s
```

Los 4 omitidos son los de integración con PostgreSQL. Los corrí aparte contra una base descartable `agro_test` (ya borrada):

```
## integración (DEV, 0.20)
4 passed in 4.30s
## detección 95% con error_rate 0.14 (APP_ENV=prod)
3 passed, 15 deselected in 1.53s
```

## 4. Qué NO pude verificar o dejé pendiente

- **Contenedores en marcha.** La configuración se copia dentro de la imagen, así que los schedulers de Docker siguen con la tasa anterior (0,20 en DEV, 0,08 en STAGING y PROD) hasta reconstruir con `docker compose up -d --build`. No lo hice en este paso; queda para el paso 6.
- **DEV mantiene `error_rate: 0.20`** (`config/environments/dev.yaml`) y su test (`test_entornos_trazas.py`) lo exige. La especificación pidió cambiar solo `config/pipeline.yaml`, así que no lo toqué. STAGING y PROD heredan el 0,14.
- **README.** Dice "Alrededor del 8 % de los registros tiene algún error". Corresponde al paso 5.
- **Test de cobertura** (`coverage report`): se corre en el paso 6.

## 5. Desvíos respecto de la especificación y por qué

**La distribución objetivo no es alcanzable hoy**, por tres motivos concretos del simulador:

1. **Tipo de error al azar y parejo.** En `iot_simulator.py` cada error elige su tipo con `rng.choice(ERROR_TYPES)`, o sea 1/13 de probabilidad para cada uno. No hay ninguna opción de configuración para darles pesos. Resultado: suelo 0,52 % (objetivo 6 %), duplicados 0,91 % (3 %), huecos 0,71 % (3 %) y "otros" 6,37 % (2 %).
2. **No existe "humedad de suelo faltante".** El simulador solo inyecta `soil_out_of_range` (valor 1,35). Un valor nulo de suelo no se genera. Hoy un nulo lo detecta únicamente DQ11 como hueco (ver pregunta abierta 1 en `docs/decisiones.md`).
3. **El duplicado no es de precipitación.** `duplicate` copia una fila completa elegida al azar; no apunta a la precipitación. Además, si un hueco o un salto no tiene lectura previa del mismo campo, el simulador lo reemplaza por `humidity_out_of_range`, lo que desvía la distribución un poco más.

**Propuesta (no implementada, necesito tu OK):**

- Agregar en `config/pipeline.yaml`, bajo `iot_simulator`, un bloque `error_mix` con el peso de cada tipo de error. Con `error_rate` 0,14 y estos pesos se cumple la distribución pedida:

  | Grupo | % de registros | Peso dentro de los errores (sobre 14 %) |
  |---|---|---|
  | Suelo faltante o fuera de rango (`soil_out_of_range` + nuevo `soil_missing`) | 6 % | 6/14 = 43 % |
  | Precipitación duplicada (`duplicate` restringido a filas con precipitación) | 3 % | 3/14 = 21 % |
  | Huecos (`gap`) | 3 % | 3/14 = 21 % |
  | Otros (`temperature_extreme`, `wrong_unit`, `bad_timestamp`) | 2 % | 2/14 = 14 % |

- Agregar el tipo nuevo `soil_missing` (humedad de suelo nula).
- Decidir qué pasa con los tipos que hoy existen y no están en tu lista: `null_timestamp`, `null_field`, `future_timestamp`, `unknown_field`, `humidity_out_of_range`, `negative_precipitation` y `spike`. Son los que ejercitan DQ01, DQ02, DQ03, DQ04, DQ07, DQ08 y DQ12. Si se los deja con peso 0, **esas siete reglas dejan de recibir casos en el simulador** y el test de detección del 95 % solo cubriría las reglas restantes. Mi sugerencia es darles un peso chico y que "otros" valga 2 % sin contar el resto, pero eso cambia tu distribución, así que lo tenés que decidir vos.
- Los 14 puntos suman 6 + 3 + 3 + 2 = 14, es decir, la distribución pedida ya cubre todo el 14 %. Eso deja **cero** margen para las otras reglas; por eso la pregunta anterior es necesaria.

Pregunta: ¿los errores de las demás reglas (DQ01–DQ04, DQ07, DQ08, DQ12) deben seguir existiendo en el simulador, o solo los cuatro grupos de tu lista?
