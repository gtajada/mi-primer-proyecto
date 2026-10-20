# Entrega práctica 3 - Bases de datos NoSQL

- **Nombre:** Gonzalo Tajada
- **student_id:** gtajada
- **Escala:** small

## CAP y PACELC

**1.** Con la red partida, la réplica `C` en modo CP devolvió error: ERROR "no disponible" al leer y ERROR "sin quórum" al escribir. En modo AP respondió `100`, un valor viejo, y aceptó la escritura de `50`. CP sacrifica disponibilidad (prefiere dar error antes que un dato desactualizado) y AP sacrifica consistencia (siempre responde, aunque el dato no sea el último).

**2.** En modo AP, después de la reparación las tres réplicas quedaron con saldo `50`. Se perdió la escritura `saldo=80` hecha en `A`, porque last-write-wins se quedó con la versión más nueva, la de `C`, y descartó la otra escritura concurrente.

**3.** Con `W=1` la p99 es 9,6 ms y con `W=3` es 55,6 ms (las p50 son 3,8 ms y 45,0 ms). Esperar a más réplicas da más consistencia, porque la escritura queda confirmada en todas las copias y una lectura posterior no ve datos viejos. A cambio sube la latencia, ya que hay que esperar a la réplica remota (+40 ms). Eso es la parte "Else" de PACELC: sin partición también hay que elegir entre latencia y consistencia.

**4.** Pudo seguir escribiendo el lado `ABC`, porque tiene 3 de las 5 réplicas y eso es mayoría (quórum). El lado `DE`, con solo 2, no pudo: la escritura en `D` dio "ERROR: sin quórum" y la lectura en `E` dio "ERROR: no disponible".

## Clave-valor

**5.** El GET en memoria tardó unos 0,0004 ms y el GET con Spark unos 582 ms, así que el notebook calcula que el dict es ~1.610.407 veces más rápido. Redis guarda los datos en memoria porque acceder a RAM con una tabla hash es órdenes de magnitud más rápido que ir a disco y planificar una consulta, y eso permite responder en milisegundos.

**6.** El valor es un JSON que la base trata como texto opaco y solo indexa por clave. Por eso, para contar los clientes de AR (992) hubo que leer y parsear los 5.000 valores. Ventaja: el GET por clave es O(1), muy rápido y fácil de repartir entre nodos. Desventaja: no se puede consultar por el contenido del valor (no hay `WHERE` ni joins), y para eso hay que mantener índices extra a mano.

**7.** Al pasar de 4 a 5 nodos, con `hash mod N` se movió el 79,6% de las claves y con hashing consistente el 21,2% (con 100 nodos virtuales). Conviene el segundo porque al agregar un nodo solo se mueven las claves de su tramo del anillo (≈1/(N+1)), y no hay que mover casi todos los datos por la red.

## Documental

**8.** La consulta relacional del cliente 42 devolvió 11 filas (3 tablas, 2 joins) y la documental devolvió 1 documento, sin joins. Dentro del documento quedaron embebidos el perfil (país, segmento, fecha de alta, email), las estadísticas (tx_count, total_amount, fraud_transactions) y las 11 transacciones, cada una con un snapshot del producto (product_id, category, price).

**9.** Spark armó un esquema que es la unión de todos los campos y completó con `null` los que faltaban en cada documento. El modelo documental tiene esquema flexible porque cada documento puede traer campos distintos (loyalty, phones, preferences, schema_version) sin definir una estructura fija ni migrar la colección antes. La estructura se infiere al leer (schema-on-read).

**10.** El documento más grande pesa 5,2 KB (≈225 bytes por transacción). A ese ritmo un cliente llegaría al límite de 16 MB de MongoDB con unas 74.626 transacciones. Si un documento crece sin límite se pasa de ese tope y además se vuelve lento de leer y actualizar, porque se trae entero aunque se necesite poco. En esos casos conviene referenciar o dividir los datos en lugar de embeberlos.

**11.** Hubo que usar `explode` porque la consulta cruza documentos y los datos están dentro de arrays, así que hay que volver a filas para agregar (por ejemplo books: 11.280 transacciones y 11.200.351,03 de monto). El modelo documental resuelve bien el acceso por entidad, o sea traer todo un cliente de una vez, y las consultas dentro de un documento sin joins, como la consulta antifraude por cliente. Le cuestan las consultas transversales entre muchos documentos y la duplicación de datos (como el snapshot del producto en cada transacción).

## Grafos

**12.** El grafo tiene 5.000 nodos `Customer`, 2.362 nodos `Device` y 5.600 aristas `USES`.

**13.** SQL necesitó 3 joins para el patrón de 2 saltos (1.494 clientes alcanzados) y 5 joins para el de 4 saltos (630 clientes). Neo4j recorre relaciones de forma más eficiente porque guarda en cada nodo punteros directos a sus vecinos (index-free adjacency): dar un salto es seguir un puntero y su costo depende de los vecinos visitados. En una base relacional cada salto es un join contra toda la tabla de aristas.

**14.** La propagación de etiquetas tardó 23 iteraciones en converger (la 23 fue la primera con 0 cambios). El componente conexo más grande tiene 62 nodos.

**15.** Con `hash(id) mod 4` el 74,5% de las aristas quedó entre máquinas distintas (con particionamiento por componente fue 0%). Es difícil distribuir un grafo porque los nodos están muy interconectados: casi cualquier forma de repartirlos corta muchas aristas, y cada arista cortada obliga a un salto por la red en los recorridos de varios saltos.

## Vectorial

**16.** El vector de cada cliente tiene 10 dimensiones que resumen su comportamiento: la proporción del gasto en cada una de las 5 categorías, la proporción de transacciones por cada uno de los 3 canales de pago, el monto promedio y la proporción de compras de ticket alto. La similitud coseno mide el ángulo entre dos vectores (1 es la misma dirección), es decir qué tan parecido es el perfil de comportamiento sin importar la magnitud.

**17.** Entre los vecinos de clientes marcados, el 31,9% también está marcado, contra una tasa base de 15,0% (entre los vecinos de los no marcados es 13,4%). Buscar vecinos parecidos sirve para encontrar clientes con comportamiento similar a uno sospechoso, por ejemplo para fraude o para clasificar con k-NN. La señal existe pero es moderada: la exactitud del clasificador (85,8%) quedó igual que predecir siempre "no marcado" (85,9%).

**18.** Con `nprobe=4` el recall@10 es 0,864 (86,4%) y se escanea el 6,09% de los vectores. Con la búsqueda aproximada se gana velocidad y menor costo, porque se revisa una fracción de los vectores en lugar de todos. Se pierde exactitud: alrededor del 14% de los vecinos verdaderos no aparece en el resultado.

## Columnar

**19.** Los datos ocupan 50,3 MB en CSV, 121,6 MB en JSON y 5,3 MB en Parquet (505.490 filas). En la consulta sobre `amount` en Parquet, Spark leyó solo esa columna (`ReadSchema: struct<amount:decimal(12,2)>`). Con los datos ordenados por `amount` se pueden saltear 7 de 8 archivos (con los datos al azar, 0 de 8).

**20.** El formato columnar es bueno para analítica porque lee solo las columnas que hacen falta, comprime mejor (Parquet ocupó 9,4 veces menos que CSV) y puede saltear bloques con las estadísticas min/max. Es poco conveniente para modificar una fila por vez porque los valores de una fila están repartidos entre columnas y archivos, así que actualizar una sola fila implica tocar y reescribir varios bloques.
