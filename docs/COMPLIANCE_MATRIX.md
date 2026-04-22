# Matriz de Cumplimiento del Proyecto Final

Este documento cruza el PDF `Final DB.pdf` con la implementacion actual de PanamaAlert.

## 1. Base de Datos Relacional (MariaDB)

- Requisito: base de datos relacional con buenas practicas y al menos 3FN.
  Evidencia:
  - `sql/01_schema.sql`
  - `app/models.py`
- Requisito: al menos 2 vistas funcionales.
  Evidencia:
  - `sql/02_views.sql`
- Requisito: al menos 2 procedimientos almacenados.
  Evidencia:
  - `sql/03_procedures.sql`
- Requisito: caso de uso practico y funcional.
  Evidencia:
  - `docs/README.md`
  - `template/mapa.html`
  - `template/dashboard.html`

## 2. API REST

- Requisito: API REST para interactuar con la base de datos.
  Evidencia:
  - `app/api/routes.py`
  - `app/main/routes.py`
- Requisito: implementar un ORM.
  Evidencia:
  - `app/models.py`
  - `app/extensions.py`
- Requisito: usar consultas crudas para operaciones avanzadas.
  Evidencia:
  - `app/main/routes.py`
  - `app/services/trust.py`
- Requisito: CRUD y buenas practicas REST.
  Evidencia:
  - `GET/POST /api/incidents`
  - `PUT/DELETE /api/incidents/<id>`
  - `POST /api/incidents/<id>/comments`
  - `POST /api/incidents/<id>/vote`

## 3. Visualizacion de Datos

- Requisito: tablero interactivo con Power BI o Tableau.
  Evidencia:
  - `bi/powerbi_connection.md`
  - `template/dashboard.html`
- Requisito: conexion en tiempo real con la base de datos.
  Evidencia:
  - vistas SQL consumibles por BI en `sql/02_views.sql`

## 4. ETL

- Requisito: proceso ETL documentado.
  Evidencia:
  - `etl/etl_pipeline.py`
  - `etl/samples/incidents_sample.csv`
- Requisito: automatizacion del ETL.
  Evidencia:
  - `docs/README.md`
  - `docs/DEPLOY_QUICKSTART.md`

## 5. Pruebas del API

- Requisito: pruebas funcionales en Postman.
  Evidencia:
  - `tests/PanamaAlert.postman_collection.json`
- Requisito: pruebas de carga con JMeter.
  Evidencia:
  - `tests/PanamaAlert_load.jmx`

## 6. Caso de Uso Integrador

- Requisito: integrar DB, API, ETL, visualizacion y pruebas.
  Evidencia:
  - `docs/README.md`
  - `docs/MANUAL_PASO_A_PASO.md`

## 7. Documentacion y Presentacion

- Requisito: diagrama ER.
  Evidencia:
  - ER en `docs/README.md`
- Requisito: explicacion del caso de uso e implementacion.
  Evidencia:
  - `docs/README.md`
- Requisito: documentacion de herramientas.
  Evidencia:
  - `bi/powerbi_connection.md`
  - `docs/MANUAL_PASO_A_PASO.md`
  - `docs/DEPLOY_QUICKSTART.md`
- Requisito: manual paso a paso.
  Evidencia:
  - `docs/MANUAL_PASO_A_PASO.md`
- Requisito: lecciones aprendidas.
  Evidencia:
  - `docs/LECCIONES_APRENDIDAS.md`
- Requisito: glosario.
  Evidencia:
  - `docs/GLOSARIO.md`

## Observaciones finales

- La solucion ya cubre los componentes principales exigidos por el PDF.
- La parte que mas conviene cuidar para la entrega es la presentacion de evidencias y no solo el codigo.
- Se recomienda exportar esta matriz junto con el README maestro al PDF final de documentacion.
