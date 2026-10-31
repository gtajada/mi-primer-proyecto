# TP Final — Big Data y MLOps

- **Estudiante:** Gonza Tajada (student_id: gtajada)
- **Variante elegida:** 1 — Investigación (caso de negocio y arquitectura de datos)
- **Extensión opcional:** incluida (sección 6, caso de MLOps con MLflow)

## Objetivo
Proponer, para una cadena de indumentaria **hipotética** (40 locales, tienda online y mayorista), una plataforma de datos tipo lakehouse con arquitectura medallion sobre Databricks, que unifique ventas y stock y alimente una sugerencia semi-automática de reposición. Es una propuesta fundamentada: **no se implementa la plataforma**. Todas las cifras son **estimaciones** con supuestos explícitos (sección 2.3 del informe).

## Contenido de la carpeta

| Archivo | Descripción |
|---|---|
| `informe.md` / `informe.pdf` | Documento principal: necesidad de negocio, datos, arquitectura, modelado, justificación, extensión MLOps y fuentes |
| `diagramas/arquitectura.png` (`.mmd`) | Diagrama de arquitectura, de la ingesta al consumo |
| `diagramas/modelo_datos.png` (`.mmd`) | Diagrama entidad-relación del modelo estrella (Gold) |
| `graficos/01_cobertura_stock.png` | Problema: cobertura de stock hoy vs. objetivo (estimación) |
| `graficos/02_volumen_estimado.png` | Volumen estimado de datos por tabla (estimación) |
| `graficos/03_resultado_esperado.png` | Metas de KPI del piloto (hipótesis) |
| `scripts/generar_graficos.py` | Script que regenera los gráficos |

## Cómo revisarlo
1. Leer `informe.pdf` (o `informe.md`, que referencia las imágenes con rutas relativas).
2. Los diagramas están en `diagramas/`; el código fuente Mermaid (`.mmd`) permite regenerarlos con `mmdc -i archivo.mmd -o archivo.png`.
3. Para regenerar los gráficos: `python scripts/generar_graficos.py` (requiere `matplotlib`).

## Datos y fuentes
No se usan datos reales ni sensibles; no hay credenciales en el repositorio. Las referencias externas están en la sección 7 del informe.
