Práctica 4 — Streaming: logs, ventanas y garantías
Campo	Valor
Nombre	Gonzalo Tajada
`student_id`	`gtajada`
Escala	`small`
Esquema	`workspace.bigdata_gtajada`
Log y offsets (`01_log_y_offsets`)
1. Después de leer tres mensajes, en la cola quedaron 2 (`pago_4`, `pago_5`) y en el log siguieron los 5, con el offset del consumidor en 3. En una cola tradicional leer borra el mensaje y sólo lo puede consumir uno; en un log como Kafka leer no modifica nada, los mensajes se conservan y cada consumidor sólo avanza su propio offset (permite varios consumidores y relectura).
2. Tras la llegada 2, `antifraude` había leído 180 mensajes (60 + 120) y `reportes` 0. El atraso de `reportes` no afectó a `antifraude` porque cada consumidor tiene su propio checkpoint (como consumer groups distintos) y el topic no se modifica al leer: hay aislamiento entre consumidores.
3. Un offset es la posición hasta la que un consumidor leyó el log. En esta práctica lo guarda cada consulta en su checkpoint, como la versión de la tabla Delta (el topic) que debe leer a continuación (al final quedó en 6, con la última versión del topic en 5).
4. El replay leyó 280 mensajes, todos los del topic (280). Kappa propone un único código de streaming y, para reprocesar, lanzar una consulta nueva con otro checkpoint que lea el log desde el principio; Lambda mantiene dos sistemas (batch preciso + capa rápida de streaming) con la misma lógica escrita dos veces.
Ingesta y enriquecimiento (`02_ingesta_y_enriquecimiento`)
5. Bronze procesó +60, +120, +40, +40 y +20 filas en las llegadas 1 a 5, y +0 al reejecutar sin archivos nuevos. Lo evita el checkpoint de Auto Loader (`cloudFiles`), que recuerda qué archivos ya leyó.
6. Aparecieron `INVALID_AMOUNT` (20 filas) y `UNKNOWN_CUSTOMER` (20 filas), ambos en la llegada `stream_002`. Bronze guarda el texto original para no perder información: si cambia el contrato o la regla de calidad, se puede reprocesar y auditar el dato crudo, en vez de descartarlo.
7. El join agregó `country` (de `silver_customers`) y `category` (de `silver_products`). Es un join stream-tabla: cada evento del stream se enriquece con una tabla estática de referencia.
Tiempo y ventanas (`03_tiempo_y_ventanas`)
8. Event time es cuándo ocurrió la compra; processing time es cuándo llega y se procesa en el sistema. `late_ok` ocurrió a las 12:03 (event time) pero llegó recién en la llegada 2, junto con eventos de las 12:06–12:08: se agrupa según las 12:03, no según cuándo llegó.
9. El watermark al terminar cada llegada fue 11:54, 11:58, 12:16, 12:17 y 12:35. Se calcula como el máximo event time visto menos 10 minutos (por ejemplo, 12:26 − 10 min = 12:16).
10. Aparecieron en la llegada 3 (4 ventanas emitidas). Antes, el watermark (11:54 y 11:58) no había superado el fin de ninguna ventana, y en append una ventana se emite recién cuando el watermark la cierra.
11. `late_bad` (12:02) llegó en la llegada 4, cuando el watermark era 12:16, así que era más viejo que el watermark y se descartó (20 eventos descartados con escala `small`). `late_ok` (12:03) llegó cuando el watermark era 11:54, es decir, todavía dentro del margen de espera de 10 minutos, y se sumó a su ventana.
12. Tumbling: ventanas fijas que no se superponen, un evento cae en una sola (ej. ventas cada 5 min). Hopping: ventanas de ancho fijo que se superponen con saltos discretos, un evento puede caer en varias (ej. promedio móvil cada 1 min sobre 10 min). Session: ancho dinámico, se cierra por inactividad (ej. sesión de navegación de un usuario).
13. Para la ventana [12:00, 12:05) del canal card, en modo update se emitió dos veces: en la llegada 1 con 40 compras y $6000, y corregida en la llegada 2 con 60 compras y $8400 (al llegar `late_ok`). En modo append se emitió una sola vez, en la llegada 3, con el valor final (60 compras, $8400). Update tiene menor latencia pero el consumidor debe tolerar correcciones y repetidos; append es más simple y final, pero con más demora.
14. Con un watermark de 1 minuto las ventanas se cerrarían antes (menos latencia y menos estado en memoria), pero los eventos tardíos como `late_ok` tendrían mucho más riesgo de descartarse y los resultados serían menos completos. Con 10 minutos se espera más y se pierden menos datos, a costa de demorar la emisión.
Garantías y fallas (`04_garantias_y_fallas`)
15. Sin deduplicar quedaron 220 filas y deduplicando por `event_id` quedaron 200 (había 20 duplicados). El productor puede reenviar un evento si no recibe confirmación o falla (at-least-once del lado del productor): ante la duda, reintenta.
16. Al reiniciar con el mismo checkpoint no se escribió nada nuevo (siguió en 200 filas), lo que se corresponde con exactly-once dentro de Spark. Al perder el checkpoint la consulta empezó de nuevo y escribió todo otra vez (400 filas), lo que se corresponde con at-least-once, con duplicados.
17. Con `MERGE` por `event_id` el resultado quedó en 200 filas tanto en la primera ejecución como con el checkpoint perdido, porque si el evento ya está no se vuelve a insertar. Una escritura idempotente es aquella en la que aplicarla una o varias veces produce el mismo resultado (por ejemplo `SET x = 5` en lugar de `x = x + 1`).
CDC (`05_cdc`)
18. El log generó 13 eventos de cambio: 6 `insert`, 3 `update_preimage`, 3 `update_postimage` y 1 `delete`. Un `UPDATE` genera dos eventos porque se registra la fila antes del cambio (`update_preimage`) y después (`update_postimage`).
19. Sí, la tabla reconstruida desde el log (quedándose con el último cambio por `customer_id` y descartando los `delete`) fue igual a la original. El log tiene la historia que la tabla actual no tiene: por ejemplo, que el cliente 2 pasó por CL antes de BR y que existió el cliente 3, que fue borrado.
Cierre
