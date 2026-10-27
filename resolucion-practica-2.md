# Resolución Práctica 2: Silver, Gold y orquestación

- **Nombre:** Gonzalo Tajada
- **student_id:** `gtajada`
- **Escala:** `small`
- **Job:** `bigdata_Gtajada_silver_gold` (Job ID `595601045452414`)

---

## 1. DAG del Job


Cuatro tareas en línea, cada una dependiente de la anterior:

```text
ingest_bronze → build_silver → build_gold → validate
```

Parámetros del Job: `student_id`, `scale`, `expected_batch_id`, `job_run_id = {{job.run_id}}`.

## 2. Resultados de las ejecuciones

| Ejecución | `expected_batch_id` | Estado | `silver_rows` | `quarantine_rows` | `gold_rows` | `gold_total_amount` | `idempotence_compared` |
|---|---|---|---:|---:|---:|---:|---|
| 1ª (run `940985645376408`) | `batch_002` | ✅ 8/8 controles | 50149 | 53 | 598 | 50,286,183.33 | `false` |
| 2ª (run `1006616552602188`, reejecución) | `batch_002` | ✅ 8/8 controles | 50149 | 53 | 598 | 50,286,183.33 | `true` |
| 3ª y siguientes | `batch_003` / `batch_004` | falló `validate` (sólo `historical_correction_applied`) | — | — | — | — | — |

En la segunda ejecución `COPY INTO` no cargó filas nuevas (`num_affected_rows = 0`), el `MERGE` no insertó ni actualizó nada y las cuatro métricas quedaron iguales a las de la primera corrida.

### Ejecuciones con `batch_003` y `batch_004`

Generé `batch_003` y después `batch_004`, y corrí el Job pasando el lote correspondiente (en el Job el parámetro figura como `expected_batch`). En esas corridas `ingest_bronze`, `build_silver` y `build_gold` terminaron bien, pero `validate` falló con:

```text
AssertionError: Fallaron controles: ['historical_correction_applied']
```

Como el `assert` corta antes de escribir la auditoría, esas corridas no dejaron fila en `pipeline_run_audit`, que tiene sólo las dos filas de `batch_002`. Las consultas sobre las tablas muestran que el procesamiento de los lotes nuevos sí fue correcto:

- `bronze_transactions_incremental` tiene 204 filas físicas por lote (pregunta 1).
- `gold_batch_summary` muestra `batch_003` y `batch_004`, y reconcilia con Silver y cuarentena (preguntas 2 y 6).
- La versión vigente de la transacción 42 en `silver_transactions` es la de `batch_004`, con `amount = 1999.99` y el `updated_at` más reciente (pregunta 4). Es exactamente lo que verifica `historical_correction_applied`.
- `silver_transactions` no tiene ids duplicados (pregunta 5).

**Causa probable de las corridas rojas.** En la columna *Run parameters* del historial se ve que el parámetro del Job se llama `expected_batch` (por ejemplo `expected_batch: batch_004`) y no `expected_batch_id`, que es el nombre del widget que lee `04_validate_pipeline`. Como los nombres no coinciden, el valor que puse en el Job nunca llegó al notebook: `validate` usó el valor por defecto del widget (`batch_002`) y exigió que la corrección de la transacción 42 viniera de `batch_002`, cuando la versión vigente ya venía de `batch_003`/`batch_004`. Es un error de configuración del Job, no del procesamiento de los datos. Corrección: renombrar el parámetro a `expected_batch_id` y reejecutar con el lote correspondiente.

## 3. `batch_002`: aceptadas y rechazadas

| Lote | Aceptadas | Rechazadas |
|---|---:|---:|
| `batch_002` | 200 | 2 (1 `INVALID_AMOUNT`, 1 `UNKNOWN_CUSTOMER`) |

De las 204 filas físicas de `batch_002`, 1 era un duplicado exacto (descartado por `dropDuplicates`), 2 fueron a cuarentena y 201 fueron válidas. Hoy figuran 200 aceptadas porque la corrección de la transacción 42 que traía `batch_002` fue reemplazada después por las de `batch_003` y `batch_004` (ver preguntas 2 y 4).

## 4. `COPY INTO` y `MERGE`: problemas diferentes

- **`COPY INTO`** trabaja a nivel de **archivo físico**. Lleva registro de qué archivos del directorio de entrada ya se cargaron y en una reejecución los saltea. Evita que el mismo CSV entre dos veces a Bronze, pero no sabe nada del contenido: si dos archivos distintos traen la misma transacción, ambos se cargan.
- **`MERGE`** trabaja a nivel de **registro de negocio** (`transaction_id`). Decide si una fila es nueva (`INSERT`), si es una versión más reciente de una existente (`UPDATE`) o si ya está aplicada (no hace nada). Resuelve duplicados y correcciones que llegan en lotes distintos.

Se necesitan los dos: `COPY INTO` da idempotencia en la ingesta y `MERGE` da idempotencia y consistencia en la tabla de negocio.

## 5. Grano de las tablas Gold

| Tabla | Grano (una fila por…) | Uso |
|---|---|---|
| `gold_daily_sales` | `sale_date` × `country` × `category` × `payment_channel` | Ventas, volumen y fraude a lo largo del tiempo |
| `gold_customer_risk` | `customer_id` (con `country` y `segment` como atributos) | Nivel de riesgo de cada cliente |
| `gold_batch_summary` | `source_batch_id` (incluye `initial`) | Calidad y volumen operativo de cada lote |

Como el grano de `gold_daily_sales` es más fino que "un día", cualquier pregunta por día, por canal o por país requiere volver a agregar (`SUM`) antes de comparar.

## 6. Visualizaciones

Código en [05_visualizacion.ipynb](05_visualizacion.ipynb).

### Consigna 1: Evolución temporal

**Respuesta:** El **2026-03-01** fue a la vez el día de mayor monto ($7.310.840,77) y el de mayor cantidad de transacciones (7.236), así que los máximos coinciden. Su ticket promedio (≈ $1.010) es similar al del resto de los días de la carga inicial (≈ $989 a ≈ $1.012): el monto lo explica el volumen, no compras más grandes. Los días 10, 11 y 12 de marzo (~200 transacciones) son los lotes incrementales y no se comparan con la carga inicial. Además, el 8 y el 9 de marzo no tienen datos.

### Consigna 2: Canal y fraude

**Respuesta:** **transfer** tiene la mayor tasa global de fraude: **13,91 %** (2.336 / 16.789), contra 12,97 % de wallet y 12,54 % de card. La conclusión se sostiene al considerar el volumen: los tres canales tienen casi la misma cantidad de transacciones (~16.800), así que la diferencia está en la tasa y no en el tamaño del canal.

### Consigna 3: Concentración geográfica y de producto

Elegí un mapa de calor porque cruza dos dimensiones categóricas en una sola figura: la celda más oscura muestra el máximo global y la ★ marca la categoría líder de cada país.

**Respuesta:** La combinación de mayor monto es **Brasil × home ($2.371.688,08)**. No hay una categoría dominante en todos los países: **home** lidera en BR, UY y CL, y **books** en AR y MX. En varios casos la diferencia es mínima (CL: home 2.171,0k contra books 2.165,5k). Fashion y electronics quedan últimas en todos los mercados.

### Consigna 4: Calidad del pipeline

**Respuesta:** `initial` tuvo **99,9 % de aceptadas** (51 rechazos sobre 49.999). `batch_002`, `batch_003` y `batch_004` tuvieron **≈ 99,0 %** cada uno (2 rechazos sobre 202, 202 y 203). En proporción, los lotes nuevos rechazan unas 10 veces más, pero son sólo 2 filas por lote.

Limitación: los lotes incrementales son muy chicos frente a `initial`, así que una o dos filas rechazadas mueven mucho su porcentaje. Además, esos lotes los arma un generador que introduce errores a propósito, así que su tasa de rechazo no representa la calidad "natural" de la fuente.

---

## 7. Preguntas de análisis y comprensión

> Todas las consultas se ejecutan en el esquema del alumno. Antes, correr
> `USE <catalogo>.<esquema>;` con el namespace que imprime `00_preflight`.

### Análisis de las tablas

#### 1. Filas físicas por lote en Bronze incremental

```sql
SELECT source_batch_id, COUNT(*) AS filas_fisicas
FROM bronze_transactions_incremental
GROUP BY source_batch_id
ORDER BY source_batch_id;
```

**Resultado:**

| source_batch_id | filas_fisicas |
|---|---:|
| batch_002 | 204 |
| batch_003 | 204 |
| batch_004 | 204 |

Cada lote tiene **204 filas físicas**: 200 transacciones nuevas, la corrección de la transacción 42, 2 registros inválidos y 1 duplicado exacto. Son filas **físicas**: incluyen el duplicado exacto y los registros inválidos que genera el generador. Bronze no filtra nada.

#### 2. Aceptadas vs. cuarentena por lote, reconciliado con Gold

```sql
WITH acc AS (
  SELECT source_batch_id, COUNT(*) AS aceptadas
  FROM silver_transactions GROUP BY source_batch_id
), rej AS (
  SELECT source_batch_id, COUNT(*) AS rechazadas
  FROM silver_transactions_quarantine GROUP BY source_batch_id
), calc AS (
  SELECT COALESCE(a.source_batch_id, r.source_batch_id) AS source_batch_id,
         COALESCE(a.aceptadas, 0) AS aceptadas, COALESCE(r.rechazadas, 0) AS rechazadas
  FROM acc a FULL OUTER JOIN rej r ON a.source_batch_id = r.source_batch_id
)
SELECT c.source_batch_id, c.aceptadas, c.rechazadas,
       g.accepted_transactions, g.rejected_transactions,
       c.aceptadas = g.accepted_transactions AND c.rechazadas = g.rejected_transactions AS reconcilia
FROM calc c FULL OUTER JOIN gold_batch_summary g ON c.source_batch_id = g.source_batch_id
ORDER BY c.source_batch_id;
```

**Resultado:**

| source_batch_id | aceptadas | rechazadas | accepted (Gold) | rejected (Gold) | reconcilia |
|---|---:|---:|---:|---:|---|
| batch_002 | 200 | 2 | 200 | 2 | true |
| batch_003 | 200 | 2 | 200 | 2 | true |
| batch_004 | 201 | 2 | 201 | 2 | true |
| initial | 49.948 | 51 | 49.948 | 51 | true |

Silver y cuarentena **reconcilian exactamente** con `gold_batch_summary` en todos los lotes. Las cuentas de cada lote incremental son 204 físicas − 1 duplicado exacto − 2 rechazadas = 201 válidas: 200 nuevas más la corrección de la 42. Sólo `batch_004` muestra 201 aceptadas porque es el único cuya versión de la 42 sigue vigente. En `batch_002` y `batch_003` la corrección fue reemplazada por una posterior y quedan 200.

En Silver, `source_batch_id` indica de qué lote viene la **versión vigente** de cada transacción. Por eso, cuando un lote corrige la transacción 42, esa fila deja de contarse en `initial` y pasa a contarse en el lote nuevo.

#### 3. Motivos de rechazo por lote

```sql
SELECT source_batch_id, quality_reason, COUNT(*) AS registros
FROM silver_transactions_quarantine
GROUP BY source_batch_id, quality_reason
ORDER BY source_batch_id, quality_reason;
```

**Resultado:**

| source_batch_id | quality_reason | registros |
|---|---|---:|
| batch_002 | INVALID_AMOUNT | 1 |
| batch_002 | UNKNOWN_CUSTOMER | 1 |
| batch_003 | INVALID_AMOUNT | 1 |
| batch_003 | UNKNOWN_CUSTOMER | 1 |
| batch_004 | INVALID_AMOUNT | 1 |
| batch_004 | UNKNOWN_CUSTOMER | 1 |
| initial | INVALID_AMOUNT | 51 |

Aparecen dos motivos. `INVALID_AMOUNT` es un importe que no se puede convertir o que no es válido, y `UNKNOWN_CUSTOMER` es un cliente que no existe en `silver_customers`. Cada lote incremental aporta exactamente uno de cada tipo, y los 51 rechazos de `initial` son todos importes inválidos.

**¿Coinciden con el generador?** Sí. El generador informó 2 registros inválidos por lote, y en cuarentena hay 2 por lote, uno de cada tipo. Los inválidos introducidos a propósito tienen que aparecer en cuarentena con su motivo (la validación exige al menos 2 por lote). Dos casos del generador **no** llegan a la cuarentena: el duplicado exacto, que elimina `dropDuplicates` antes de validar, y la corrección de la 42, que es válida y entra a Silver mediante `UPDATE`.

#### 4. Linaje de la transacción 42

```sql
SELECT transaction_id, source_batch_id, amount, event_ts,
       try_cast(updated_at AS TIMESTAMP) AS updated_at
FROM bronze_transactions_all
WHERE transaction_id = '42'
ORDER BY updated_at;

SELECT transaction_id, amount, source_batch_id, event_ts, updated_at, processed_at
FROM silver_transactions
WHERE transaction_id = 42;
```

**Resultado:**

Bronze (`bronze_transactions_all`): **4 versiones**

| source_batch_id | amount | event_ts | updated_at |
|---|---:|---|---|
| initial | 600.11 | 2026-03-06 02:07:52 | 2026-03-06 02:07:52 |
| batch_002 | 1999.99 | 2026-03-10 00:00 | 2026-03-10 02:00:00 |
| batch_003 | 1999.99 | 2026-03-11 00:00 | 2026-03-11 02:00:00 |
| batch_004 | 1999.99 | 2026-03-12 00:00 | 2026-03-12 02:00:00 |

Silver (`silver_transactions`): **1 fila**, `source_batch_id = batch_004`, `amount = 1999.99`, `updated_at = 2026-03-12 02:00:00`.

Queda vigente la versión con el `updated_at` más reciente (`batch_004`). En la versión `initial`, `updated_at` es igual a `event_ts` (ver pregunta 13), y cada corrección posterior trae un `updated_at` mayor. Lo justifican las columnas `updated_at` y `source_batch_id`: el `row_number` ordena por `updated_at DESC`, desempata por `source_batch_id DESC`, y el `MERGE` sólo actualiza si `s.updated_at > t.updated_at`.

#### 5. Una fila por `transaction_id` en Silver

```sql
SELECT COUNT(*) AS filas, COUNT(DISTINCT transaction_id) AS ids_distintos
FROM silver_transactions;

SELECT transaction_id, COUNT(*) AS veces
FROM silver_transactions
GROUP BY transaction_id
HAVING COUNT(*) > 1;
```

**Resultado:** `filas = 50.549` e `ids_distintos = 50.549`. La consulta de duplicados **no devuelve filas**, así que hay una sola fila por `transaction_id`. Además, 50.549 = 49.948 + 200 + 200 + 201, la suma de aceptadas por lote de la pregunta 2.

La deduplicación falló si `filas > ids_distintos` o si la segunda consulta devuelve alguna fila. Es el mismo control que `silver_no_duplicate_ids` en `04_validate_pipeline`.

#### 6. Tasa de rechazo por lote

```sql
SELECT source_batch_id, accepted_transactions, rejected_transactions,
       accepted_transactions + rejected_transactions AS total,
       ROUND(rejected_transactions / (accepted_transactions + rejected_transactions), 4) AS tasa_rechazo
FROM gold_batch_summary
ORDER BY source_batch_id;
```

**Resultado:**

| source_batch_id | aceptadas | rechazadas | total | tasa_rechazo |
|---|---:|---:|---:|---:|
| batch_002 | 200 | 2 | 202 | 0,0099 |
| batch_003 | 200 | 2 | 202 | 0,0099 |
| batch_004 | 201 | 2 | 203 | 0,0099 |
| initial | 49.948 | 51 | 49.999 | 0,0010 |

`batch_004` tiene 201 aceptadas porque la versión vigente de la transacción 42 es la suya (ver pregunta 4). Las correcciones de `batch_002` y `batch_003` fueron reemplazadas y ya no cuentan como vigentes.

No es correcto comparar sólo cantidades absolutas: `initial` tiene 51 rechazos contra 2 de cada lote, lo que sugiere que es "peor", pero en proporción es al revés (0,1 % contra 1 %). `initial` tiene muchas más filas que los lotes incrementales, así que puede tener más rechazos en número y aun así una tasa menor. La tasa normaliza por el tamaño del lote. Aun así conviene informar el `total`, porque en lotes chicos una sola fila cambia mucho la tasa.

#### 7. Día de mayor monto vs. día de mayor cantidad

```sql
WITH d AS (
  SELECT sale_date, SUM(total_amount) AS monto, SUM(transaction_count) AS transacciones,
         SUM(total_amount) / SUM(transaction_count) AS ticket_promedio
  FROM gold_daily_sales
  GROUP BY sale_date
)
(SELECT 'mayor_monto' AS criterio, * FROM d ORDER BY monto DESC LIMIT 1)
UNION ALL
(SELECT 'mayor_cantidad' AS criterio, * FROM d ORDER BY transacciones DESC LIMIT 1);
```

**Resultado:** los dos criterios dan el **2026-03-01**: $7.310.840,77 y 7.236 transacciones (ticket promedio ≈ $1.010,34). **Sí coinciden.**

Primero hay que agregar por día, porque cada fila de `gold_daily_sales` es día × país × categoría × canal. Si los máximos no coinciden, el ticket promedio de esos días es distinto: un día con pocas compras grandes puede superar en monto a uno con muchas compras chicas.

#### 8. Canal con mayor tasa global de fraude

```sql
SELECT payment_channel,
       SUM(fraud_transactions) AS fraudes,
       SUM(transaction_count) AS transacciones,
       SUM(fraud_transactions) / SUM(transaction_count) AS tasa_global,
       AVG(fraud_rate) AS promedio_simple_incorrecto
FROM gold_daily_sales
GROUP BY payment_channel
ORDER BY tasa_global DESC;
```

**Resultado:**

| payment_channel | fraudes | transacciones | tasa_global | promedio_simple_incorrecto |
|---|---:|---:|---:|---:|
| transfer | 2.336 | 16.789 | **0,1391** | 0,1347 |
| wallet | 2.178 | 16.791 | 0,1297 | 0,1274 |
| card | 2.128 | 16.969 | 0,1254 | 0,1241 |

El canal con mayor tasa global es **transfer (13,91 %)**.

`fraud_rate` es una razón calculada en cada grupo día × país × categoría × canal, y cada grupo tiene un denominador distinto. Promediarla le da el mismo peso a un grupo de 1 transacción (que puede tener 0 % o 100 %) que a uno de cientos, y sesga el resultado. Lo correcto es sumar numeradores y denominadores y dividir al final, lo que equivale a un promedio ponderado por `transaction_count`. La columna `promedio_simple_incorrecto` muestra la diferencia: en los tres canales el promedio simple **subestima** la tasa real (en transfer, 13,47 % contra 13,91 %). Acá el ranking no cambia, pero con grupos de tamaños más desparejos podría invertirse.

#### 9. País × categoría con mayor monto

```sql
-- Máximo global
SELECT country, category, SUM(total_amount) AS monto
FROM gold_daily_sales
GROUP BY country, category
ORDER BY monto DESC
LIMIT 1;

-- Líder dentro de cada país
WITH cc AS (
  SELECT country, category, SUM(total_amount) AS monto
  FROM gold_daily_sales
  GROUP BY country, category
)
SELECT country, category, monto
FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY country ORDER BY monto DESC) AS rn FROM cc)
WHERE rn = 1
ORDER BY monto DESC;
```

**Resultado:** máximo global **BR × home = $2.371.688,08**.

| country | categoría líder | monto |
|---|---|---:|
| BR | home | 2.371,7k |
| UY | home | 2.330,2k |
| AR | books | 2.272,9k |
| MX | books | 2.244,3k |
| CL | home | 2.171,0k |

#### 10. Auditoría de la reejecución de `batch_002`

```sql
SELECT job_run_id, expected_batch_id, silver_rows, quarantine_rows,
       gold_rows, gold_total_amount, recorded_at, idempotence_compared
FROM pipeline_run_audit
WHERE expected_batch_id = 'batch_002'
ORDER BY recorded_at
LIMIT 2;
```

**Resultado:**

| job_run_id | expected_batch_id | silver_rows | quarantine_rows | gold_rows | gold_total_amount | recorded_at | idempotence_compared |
|---|---|---:|---:|---:|---:|---|---|
| 940985645376408 | batch_002 | 50149 | 53 | 598 | 50286183.33 | 2026-10-03 13:18:19 UTC | `false` |
| 1006616552602188 | batch_002 | 50149 | 53 | 598 | 50286183.33 | 2026-10-03 13:23:33 UTC | `true` |

Quedan iguales `silver_rows`, `quarantine_rows`, `gold_rows` y `gold_total_amount`. Cambian `job_run_id` y `recorded_at`, porque son dos corridas distintas. La columna que demuestra la comparación es **`idempotence_compared`**: vale `false` en la primera fila (no había una corrida anterior del mismo lote para comparar) y `true` en la segunda. Para que quede en `true`, el `assert current_metrics == prior_metrics` de `04_validate_pipeline` (celda de auditoría) tuvo que pasar.

### Interpretación del código y del pipeline

#### 11. `COPY INTO` (`01_ingest_bronze_incremental`, celda 4)

Resuelve la **ingesta incremental idempotente**: carga en `bronze_transactions_incremental` sólo los archivos del directorio `incoming/transactions/` que todavía no se cargaron. Sin esto habría que llevar a mano qué archivos se procesaron, o se duplicarían filas en cada reejecución. Delta guarda en el estado de la tabla destino la **ruta de cada archivo ya cargado**. En una nueva ejecución compara el listado del directorio contra ese registro y saltea los archivos conocidos (salvo que se use `COPY_OPTIONS ('force' = 'true')`). Por eso la segunda corrida informa 0 filas afectadas. El generador escribe un CSV "estable" por lote, con un nombre fijo, justamente para aprovechar esto.

#### 12. `UNION ALL` en `bronze_transactions_all` (`01_ingest_bronze_incremental`, celda 5)

Bronze tiene que conservar **todo lo que llegó, tal cual llegó**, para auditar y reprocesar. `UNION` (sin `ALL`) eliminaría duplicados exactos y perdería esa evidencia, y además costaría un shuffle. Tampoco resolvería el problema real: una corrección no es un duplicado exacto (cambian `amount`, `updated_at` y `source_batch_id`), así que `UNION` la dejaría pasar igual. Los duplicados de negocio se resuelven en **Silver** (`02_build_silver`, celda 6): `dropDuplicates` elimina los duplicados exactos y `row_number` por `_record_key` elige la versión vigente. Decidir qué versión gana es una regla de negocio y corresponde a la capa de datos confiables, no a la de datos crudos.

#### 13. `source_batch_id='initial'` y `updated_at = event_ts` (`01_ingest_bronze_incremental`, celda 5)

La tabla `bronze_transactions` de la práctica 1 no tiene columnas de lote ni de versión. La vista las completa para que ambas fuentes tengan el mismo esquema:

- `'initial'` identifica de dónde viene la fila. Sirve para el linaje y para agrupar en `gold_batch_summary`.
- `event_ts` como `updated_at` da una fecha de versión razonable: la versión original de una transacción "se actualizó" cuando ocurrió.

En la transacción 42, la corrección del lote nuevo trae un `updated_at` posterior a su `event_ts` original. Por eso gana en el `row_number` (`updated_at DESC`) y cumple la condición del `MERGE` (`s.updated_at > t.updated_at`), lo que produce un `UPDATE` real. Si la carga inicial tuviera `updated_at` nulo o futuro, la comparación fallaría y la corrección nunca se aplicaría.

#### 14. `try_cast` frente a `cast` (`quality_rules.py`, `add_transaction_types`)

Con ANSI SQL activo (el modo por defecto en serverless), `cast('N/A' AS DECIMAL)` **lanza un error** y hace fallar toda la tarea por una sola fila mala. `try_cast` devuelve **`NULL`** y el pipeline sigue. Ese `NULL` en `amount_typed` lo detecta después una regla de calidad, y el registro va a cuarentena con su motivo. Como la cuarentena guarda las columnas crudas (`STRING`), se conserva el valor original `N/A` para diagnosticar.

#### 15. Una única `quality_reason` y el orden de las reglas (`quality_rules.py`, `add_quality_reason`)

`add_quality_reason` arma una cadena `F.when(...).when(...)...`. Spark evalúa las condiciones en orden y asigna la **primera que se cumple**. Si un registro viola varias reglas, sólo queda registrada la primera; las demás no aparecen. El orden no cambia **cuántos** registros se rechazan (alcanza con violar una regla), pero sí **qué motivo** se informa y, por lo tanto, los conteos por motivo de la pregunta 3. Conviene poner primero las reglas más básicas (id no numérico, campos obligatorios nulos, tipos inválidos) y después las de integridad referencial (cliente o producto desconocido). Así el motivo apunta a la causa raíz: si el `customer_id` no es numérico, decir "cliente desconocido" sería engañoso.

#### 16. `_record_key` y `row_number` (`02_build_silver`, celda 6)

```python
record_key = F.coalesce(
    F.col("transaction_id_typed").cast("string"),
    F.sha2(F.concat_ws("||", *[F.coalesce(F.col(c), F.lit("<NULL>")) for c in raw_columns]), 256))
```

- Si `transaction_id` se pudo convertir a número, la clave es ese id. Todas las versiones de una misma transacción comparten clave.
- Si no se pudo (`NULL`, `abc`, etc.), la clave es un **SHA-256 de todas las columnas crudas**. Los nulos se reemplazan por `<NULL>` porque `concat_ws` los omitiría y dos filas distintas podrían dar el mismo texto.

Después, `row_number()` se particiona por `_record_key`, se ordena por `updated_at_typed DESC NULLS LAST, source_batch_id DESC` y se queda con `_rn = 1`: la versión más reciente de cada clave.

El hash cubre los registros **sin id válido**. Sin él, todos tendrían clave `NULL`, caerían en la misma partición y sólo sobreviviría uno: los demás desaparecerían sin llegar siquiera a la cuarentena. Con el hash, cada registro inválido distinto conserva su propia clave y todos quedan en cuarentena. Dos filas con el mismo hash serían duplicados exactos, que `dropDuplicates` ya eliminó antes.

#### 17. El `MERGE` de `silver_transactions` (`02_build_silver`, celda 7)

```sql
MERGE INTO silver_transactions t USING _valid_transactions s ON t.transaction_id = s.transaction_id
WHEN MATCHED AND s.updated_at > t.updated_at THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
```

- **`WHEN MATCHED AND s.updated_at > t.updated_at` → `UPDATE`:** el id ya existe en Silver y la fuente trae una versión **más nueva**. Es el caso de la corrección de la 42.
- **`WHEN NOT MATCHED` → `INSERT`:** el id no existe en Silver, es una transacción nueva.
- Si el id existe pero la versión no es más nueva (por ejemplo, en una reejecución), no pasa nada. Esto da la **idempotencia**: reprocesar no duplica ni pisa datos. Como no hay `WHEN NOT MATCHED BY SOURCE`, el `MERGE` nunca borra filas.

#### 18. Gold completo vs. Silver con `MERGE` (`03_build_gold` y `02_build_silver`)

| Estrategia | Ventaja | Limitación |
|---|---|---|
| **Gold con `CREATE OR REPLACE`** | Simple y determinista: siempre refleja exactamente el estado actual de Silver, incluidas correcciones, sin lógica incremental ni riesgo de doble conteo. | Recalcula toda la historia en cada corrida, así que el costo crece con el volumen total y no con lo nuevo. |
| **Silver con `MERGE`** | Procesa sólo lo nuevo o lo cambiado, mantiene una fila por clave, aplica correcciones y conserva el historial en Delta (`DESCRIBE HISTORY`). | Más complejo: la corrección depende de elegir bien la clave y la condición de actualización, y no propaga borrados. |

En esta práctica los volúmenes son chicos y Gold son agregados que dependen de toda la historia (una corrección cambia sumas ya publicadas), así que reconstruirlo es lo más seguro. Silver, en cambio, es la tabla donde vive la identidad de cada registro.

#### 19. `expected_batch_id` no detecta archivos

La detección la hace **`COPY INTO` en `01_ingest_bronze_incremental` (celda 4)**: lee el directorio `incoming/transactions/` completo y carga cualquier archivo no procesado, sin importar el nombre del lote. `batch_003` entra porque es un archivo nuevo, no porque alguien lo pidió.

El parámetro lo usa **`04_validate_pipeline`** para decir qué lote se espera verificar: que llegó a Bronze y a Silver, que tiene rechazos controlados, que aparece en `gold_batch_summary`, que la 42 quedó corregida por ese lote, y para decidir si la corrida es comparable con la anterior en la auditoría. Detalle: `01_ingest_bronze_incremental` (celda 5) también lee el parámetro, pero sólo como precondición (`assert found > 0`) **después** del `COPY INTO`; no interviene en qué se carga. `02` y `03` declaran el widget pero no lo usan.

Me pasó en la práctica, aunque por una causa de configuración: el Job tenía el parámetro con el nombre `expected_batch` y no `expected_batch_id`, así que el notebook usó siempre el valor por defecto `batch_002`, equivalente a haber corrido con `expected_batch_id = batch_002` después de generar `batch_003`. `ingest_bronze`, `build_silver` y `build_gold` terminaron bien y `batch_003` se procesó, pero `validate` falló con `AssertionError: Fallaron controles: ['historical_correction_applied']`. Los controles de `batch_002` pasaban porque sus datos seguían en las tablas. En cambio, la versión vigente de la transacción 42 ya venía de `batch_003`, y el control exigía `source_batch_id = 'batch_002'`. El rojo indicaba una expectativa de prueba desactualizada, no una falla del pipeline. Como el `assert` corta antes de escribir la auditoría, esa corrida no dejó fila en `pipeline_run_audit`.

#### 20. Falla de `build_silver`

En el DAG, `build_gold` depende de `build_silver` y `validate` de `build_gold`, con la condición por defecto (*all succeeded*). Si `build_silver` falla, **`build_gold` y `validate` no se ejecutan**: quedan como *Upstream failed* / omitidas y el Job termina en rojo.

- Gold **no se reconstruye** a partir de un Silver a medio actualizar, así que sigue publicando la versión anterior, completa y consistente.
- `validate` no corre, así que no se valida un estado incompleto ni se escribe una fila engañosa en `pipeline_run_audit`.

Lo vi en la práctica: en el primer intento del run `940985645376408`, `ingest_bronze` falló con `[PATH_NOT_FOUND] .../landing/incoming/transactions` porque todavía no había corrido el generador. `build_silver`, `build_gold` y `validate` quedaron en *Upstream failed* con 0 s de duración, sin tocar ninguna tabla. Después de generar `batch_002`, un **Repair run** volvió a ejecutar sólo lo pendiente y las cuatro tareas terminaron bien.


Como cada `MERGE` sobre Delta es atómico, una sentencia que falla no deja filas a medias. Puede pasar, eso sí, que `silver_transactions` se haya actualizado y la cuarentena no. Al reejecutar, el `MERGE` idempotente completa lo que falta sin duplicar.
