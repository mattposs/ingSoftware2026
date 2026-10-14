# Revisión del paso 4: test de "Gold sin inválidos"

## 1. Qué pediste vs. qué hiciste

| Ítem de la especificación | Qué hice |
|---|---|
| Reforzar `tests/test_integration_db.py::test_gold_no_tiene_registros_invalidos` | Reforzado (ver los cuatro ítems siguientes). Los chequeos de rangos que ya tenía se conservaron. |
| Todo `field_id` de Gold existe en `gold.fields` | Agregado: `set(df["field_id"]) <= known_fields`, leyendo ambas tablas de la base. |
| `(fecha, field_id, fuente)` es única en `daily_field_metrics` | Agregado: `assert not df.duplicated(subset=gold.GOLD_KEYS).any()`. |
| Ninguna clave de Gold coincide con un registro en quarantine | Agregado con una interpretación que explico en la sección 5: ningún registro de Quarantine (salvo los rechazados solo por DQ05) tiene la misma identidad `(source, field_id, timestamp)` que uno de Silver, y la `cantidad_mediciones` de cada fila de Gold es igual a la cantidad de filas de Silver de esa clave. |
| Test nuevo: inyectar un duplicado de precipitación y verificar que `precipitacion_total` NO se duplica | `test_precipitacion_duplicada_no_se_suma_y_el_segundo_registro_va_a_quarantine`: dos lecturas idénticas con precipitación 5,0; Gold queda con `precipitacion_total` = 5,0 (no 10,0) y `cantidad_mediciones` = 1. |
| …y que el segundo registro termina en quarantine con motivo DQ05 | El mismo test verifica 1 fila en Silver, 1 fila en Quarantine con `_rejection_reasons` = `DQ05` y un único hallazgo `DQ05` / `REJECT` en `gold.dq_errors`. Además comprueba `porcentaje_calidad` = 50,0 (1 VALID de 2). |

## 2. Archivos cambiados y hash del commit

El hash se informa en el chat (un commit no puede contener su propio hash); se ve con `git log --oneline -3`. Commit padre: `9f711b9`.

- `tests/test_integration_db.py`
- `docs/revision/paso-4.md` (este archivo)

No hubo cambios de código de producción en este paso.

## 3. Comandos que corrí y su salida real

`ruff check .`:

```
All checks passed!
```

Los tests de este archivo necesitan PostgreSQL. Los corrí contra una base descartable `agro_test` con el esquema actual (`TEST_DATABASE_URL` apuntando a ella), nunca contra `agro_dev`, `agro_staging` ni `agro_prod`:

```
tests\test_integration_db.py .....                                       [100%]
============================== 5 passed in 6.99s ==============================
```

Suite completa con la base disponible:

```
........................................................................ [ 78%]
....................                                                     [100%]
92 passed in 25.10s
```

**Prueba de que el test nuevo detecta el problema** (mutación): desactivé temporalmente la regla DQ05 en `src/validation/engine.py` (reemplacé la línea que rechaza el duplicado por un `pass`) y corrí solo el test del duplicado. Falló, como corresponde:

```
[DQ] total=2 valid=2 warning=0 invalid=0 score=100.0% utilizable=100.0% errores=0
...
tests\test_integration_db.py:152: assert 10.0 == 5.0
FAILED tests/test_integration_db.py::test_precipitacion_duplicada_no_se_suma_y_el_segundo_registro_va_a_quarantine
1 failed, 4 deselected in 2.36s
```

Con la regla rota, la precipitación se duplica a 10,0, que es exactamente el error que el test quiere atrapar. Restauré `engine.py` (`git diff` sin diferencias) antes de seguir.

## 4. Qué NO pude verificar o dejé pendiente

- **No hice una mutación del test reforzado `test_gold_no_tiene_registros_invalidos`.** Probé que pasa con datos correctos y que el test del duplicado detecta una regla rota, pero no probé que cada uno de los tres chequeos nuevos (campos existentes, claves únicas, Quarantine) falle por separado cuando se rompe lo que vigilan. La base ya impone dos de ellos con restricciones (`FOREIGN KEY` hacia `gold.fields` y `PRIMARY KEY (fecha, field_id, fuente)`), así que esos dos son redundantes con el esquema; el tercero es el que depende del código.
- **Los tests con PostgreSQL no corren en la suite local sin `TEST_DATABASE_URL`** (se omiten); en el CI corren contra el servicio postgres del workflow. No ejecuté el CI de GitHub.
- **Base `agro_test` sin borrar.** Al terminar quise borrar la base descartable `agro_test` pero Docker se detuvo en ese momento (los contenedores del stack aparecen como `Exited` y el log de PostgreSQL decía "the database system is shutting down"). No fui yo quien los detuvo. `agro_test` queda en el volumen hasta que se levante el stack de nuevo; la borro en el paso 6.
- Los datos de los campos viejos `C01`–`C06` siguen en las bases del stack (ver paso 1).

## 5. Desvíos respecto de la especificación y por qué

1. **"Ninguna clave de Gold coincide con un registro en quarantine"** admite dos lecturas y elegí la segunda:
   - *Lectura literal:* ninguna fila de Gold, con clave `(fecha, campo, fuente)`, tiene registros en Quarantine. Es **falsa por diseño**: un día con lecturas válidas y rechazadas del mismo campo tiene a la vez fila en Gold y registros en Quarantine, y el porcentaje de calidad diario se calcula justamente con esos rechazados.
   - *Lectura implementada:* ningún registro rechazado puede estar en Silver (misma identidad `source, field_id, timestamp`), y Gold cuenta exactamente lo que hay en Silver, de modo que lo rechazado nunca entra a los promedios.
   - Si te referías a otra cosa, decime y lo cambio.
2. **Se excluyen los rechazos "solo DQ05" de la comparación de identidad**, porque un duplicado tiene la misma identidad que su original (que sí es válido y sí está en Silver). Sin esa exclusión el test fallaría con cualquier duplicado inyectado por el simulador.
3. **El duplicado del test nuevo es una lectura completa repetida** (todas las variables iguales), no una fila con solo la precipitación repetida, porque así funciona DQ05: la clave es `(source, field_id, timestamp)`.
