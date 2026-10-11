# Práctica 1 — Ingesta y capa Bronze

| Campo | Valor |
|---|---|
| Nombre | Gonzalo Tajada |
| `student_id` | `gtajada` |
| Escala | `small` |
| Esquema | `workspace.bigdata_gtajada` |
| Volumen | `workspace.bigdata_gtajada.landing` (`/Volumes/workspace/bigdata_gtajada/landing`) |

## Tablas Bronze generadas

| Tabla | Filas | Formato de origen |
|---|---:|---|
| `bronze_customers` | 5.000 | CSV |
| `bronze_products` | 500 | Parquet |
| `bronze_transactions` | 50.011 | CSV |
| `bronze_events` | 200.000 | JSON |

Diagnóstico de calidad sobre `bronze_transactions`:

| rows | distinct_ids | invalid_amounts |
|---:|---:|---:|
| 50.011 | 50.000 | 52 |

## 1. Tres observaciones sobre CSV/JSON, Parquet y Delta

**1. CSV y JSON no garantizan tipos; Parquet sí.**
CSV es texto plano: sin un esquema explícito, Spark lee todas las columnas como `string`, incluidos `amount`, `event_ts` e `is_fraud`. JSON permite inferir tipos básicos (`long`) y representar estructuras anidadas (`context` es un `struct` con `platform` y `session_id`), pero no tiene tipo fecha (`event_ts` queda como `string`). Parquet guarda el esquema en los metadatos del archivo: `price` llega como `decimal(12,2)` y `product_id` como `long` sin ninguna inferencia. Además, `product_id` es `long` en Parquet/JSON y `string` en el CSV de transacciones, por lo que hay que alinear tipos antes de unir tablas en Silver.

**2. Inferir el esquema cuesta y es inestable.**
Con `inferSchema=true`, Spark hace una pasada completa extra sobre el CSV para decidir los tipos. El resultado depende del contenido del lote y no de un contrato: `transaction_id` queda `integer` (contra `long` en Parquet/JSON), `is_fraud` queda `integer` aunque semánticamente es booleano, y `amount` sigue siendo `string` porque contiene valores no numéricos. Un lote futuro con un ID más grande o una fecha malformada cambiaría los tipos. Por eso conviene declarar el esquema o, en Bronze, conservar el dato como texto y validarlo en Silver.

**3. Delta agrega una capa de tabla sobre Parquet.**
Físicamente los datos siguen siendo Parquet (el plan muestra `PhotonScan parquet`, compresión `zstd`), pero Delta suma un *transaction log* con:
- **Historial versionado:** `DESCRIBE HISTORY` muestra dos versiones (v0 del 26/09 y v1 de hoy), cada una con usuario, notebook, operación y filas escritas. Al sobrescribir, el archivo anterior se marca como removido (`numRemovedFiles: 1`) en lugar de borrarse, lo que permite *time travel* (`VERSION AS OF 0`).
- **Metadatos de tabla:** protocolo (`minReaderVersion`/`minWriterVersion`), propiedades y features como *deletion vectors*.
- **Lecturas optimizadas:** el plan usa `PreparedDeltaFileIndex` (consulta el log en vez de listar el directorio), lee solo la columna necesaria (`ReadSchema: struct<payment_channel:string>`, *column pruning*) y cuenta con estadísticas completas para el optimizador.

Un directorio Parquet suelto no tiene historial, auditoría ni garantías transaccionales.

## 2. Las cinco V en este caso

- **Volumen:** 255.511 filas entre las cuatro fuentes (200.000 solo en eventos). En escala `small` no es Big Data, pero el mismo código corre sin cambios en `demo` o sobre TB, porque Spark distribuye el procesamiento.
- **Velocidad:** `events` es la fuente que se genera más rápido (4 veces más filas que `transactions`): son interacciones de usuarios con `event_ts` y `session_id`, datos que en un sistema real llegan de forma continua. La columna `_ingested_at` permite medir la frescura de cada carga.
- **Variedad:** tres formatos (CSV, JSON, Parquet) con distintos niveles de estructura: texto plano sin tipos, JSON semi-estructurado con campos anidados y Parquet columnar con esquema embebido.
- **Veracidad:** `bronze_transactions` tiene 50.011 filas pero solo 50.000 `transaction_id` distintos (11 duplicados) y 52 importes que no pueden convertirse a `DECIMAL(12,2)`. Además, los tipos de `product_id` no coinciden entre fuentes. Bronze conserva estos problemas como evidencia y se corrigen en Silver.
- **Valor:** cruzando transacciones, clientes, productos y eventos se puede analizar ventas por canal de pago y categoría, entender el comportamiento previo a la compra y detectar fraude (`is_fraud`). Ese valor solo es confiable si antes se resuelven los problemas de veracidad: sumar importes desde Bronze inflaría las ventas por los duplicados.
