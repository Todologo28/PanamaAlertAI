# Caso de Uso y Cumplimiento de Requisitos

## 1. Nombre del proyecto

PanamaAlert: plataforma de inteligencia ciudadana para reportar, visualizar y analizar alertas geolocalizadas en Panama.

## 2. Problema identificado

La informacion sobre incidentes ciudadanos, seguridad, emergencias, trafico, reportes comunitarios y ofertas relevantes suele encontrarse dispersa entre redes sociales, noticias, usuarios y fuentes externas. Esto dificulta que los ciudadanos, autoridades, analistas o empresas tengan una vista centralizada, geolocalizada y actualizada.

PanamaAlert resuelve este problema mediante una aplicacion web que permite visualizar pings en un mapa, registrar incidentes, consultar informacion, analizar zonas y conectar los datos a Power BI para seguimiento administrativo.

## 3. Actores del sistema

- Usuario publico: puede entrar sin cuenta y visualizar el mapa con alertas publicas.
- Usuario registrado: puede iniciar sesion, reportar incidentes, consultar detalles y configurar preferencias.
- Administrador o moderador: puede gestionar incidentes, revisar informacion y administrar el sistema.
- Bot o agente de ofertas/noticias: consulta fuentes externas, transforma informacion y crea pings geolocalizados.
- Analista BI: consume las vistas de MariaDB desde Power BI mediante ODBC.

## 4. Flujo principal del caso de uso

1. El usuario entra a PanamaAlert.
2. Si no inicia sesion, puede ver el mapa publico con alertas y ofertas sin ver datos privados del publicador.
3. Si inicia sesion, puede crear incidentes desde el mapa o mediante busqueda de ubicacion.
4. El backend recibe la solicitud por API REST.
5. La informacion se valida, se procesa y se almacena en MariaDB.
6. Las vistas SQL preparan los datos para reportes administrativos y Power BI.
7. El proceso ETL/bot extrae datos desde fuentes externas, limpia el contenido, detecta ubicacion y carga pings como incidentes verificados.
8. Power BI se conecta por ODBC a la misma base de datos y actualiza las visualizaciones.
9. Postman valida los endpoints funcionales de la API.
10. JMeter ejecuta pruebas de carga sobre endpoints del sistema.

## 5. Cumplimiento de requisitos

### 5.1 Base de Datos Relacional MariaDB

Se implemento una base de datos relacional en MariaDB. El modelo esta separado por entidades como usuarios, roles, incidentes, categorias, provincias, distritos, comentarios, votos, sesiones, auditoria, suscripciones de alerta, analisis IA, llaves API y ejecuciones ETL.

Evidencia:

- `sql/01_schema.sql`
- `app/models.py`

La estructura aplica normalizacion hasta tercera forma normal porque cada entidad mantiene atributos propios, se evita redundancia innecesaria y las relaciones se manejan mediante llaves foraneas.

### 5.2 Vistas funcionales

El proyecto supera el requisito minimo de dos vistas. Se implementaron vistas para consumo operativo y Power BI:

- `v_incidents_full`: incidentes con categoria, usuario, distrito, provincia, votos y comentarios.
- `v_incidents_daily_stats`: resumen diario por provincia, distrito y categoria.
- `v_user_activity`: actividad de usuarios, plan, reportes y retencion.
- `v_hotspots`: agrupacion geografica para mapa de calor.
- `v_bi_overview_kpis`: indicadores principales para tarjetas Power BI.
- `v_bi_category_summary`: resumen por categoria.

Evidencia:

- `sql/02_views.sql`

### 5.3 Procedimientos almacenados

Se implementaron procedimientos almacenados para tareas relevantes del caso de uso:

- `sp_create_incident`: creacion controlada de incidentes.
- `sp_verify_incident`: verificacion o moderacion de incidentes.
- `sp_nearby_incidents`: consulta de incidentes cercanos.
- `sp_upgrade_plan`: cambio de plan de usuario.
- `sp_rate_limit_check`: validacion de limites de uso.

Evidencia:

- `sql/03_procedures.sql`

### 5.4 API REST

La aplicacion expone endpoints REST para interactuar con la base de datos. Se usan verbos HTTP como GET, POST, PUT y DELETE para consultar, crear, actualizar y eliminar recursos.

Ejemplos:

- `GET /api/incidents`
- `POST /api/incidents`
- `GET /api/incidents/<id>`
- `PUT /api/incidents/<id>`
- `DELETE /api/incidents/<id>`
- `POST /api/incidents/<id>/comments`
- `POST /api/incidents/<id>/vote`

Evidencia:

- `app/api/routes.py`
- `app/main/routes.py`

### 5.5 ORM

El ORM utilizado es SQLAlchemy mediante Flask-SQLAlchemy. Las tablas principales tienen representacion como modelos Python.

Evidencia:

- `app/models.py`
- `app/extensions.py`

### 5.6 Consultas crudas

Ademas del ORM, el backend utiliza consultas SQL directas para operaciones avanzadas, estadisticas, vistas, seguridad, sesiones y analisis.

Evidencia:

- `app/main/routes.py`
- `app/api/routes.py`
- `app/services/trust.py`

### 5.7 Visualizacion de datos

Se utiliza Power BI conectado por ODBC a MariaDB. El tablero consume vistas preparadas para indicadores, mapa, tendencias, categorias, usuarios y hotspots.

Vistas recomendadas para Power BI:

- `v_bi_overview_kpis`
- `v_bi_category_summary`
- `v_incidents_full`
- `v_incidents_daily_stats`
- `v_hotspots`
- `v_user_activity`

Evidencia:

- `bi/powerbi_connection.md`
- `bi/powerbi_dashboard_layout.md`
- `bi/powerbi_measures.dax`

### 5.8 ETL

El ETL extrae informacion desde fuentes externas, limpia texto, identifica ofertas o noticias, resuelve ubicacion, transforma el contenido y lo carga como pings/incidentes en la base de datos.

Evidencia:

- `etl/etl_pipeline.py`
- `app/services/news_ingest.py`
- `app_data/news/sources.json`
- `etl_runs`

### 5.9 Pruebas Postman

Se incluye una coleccion Postman para probar funcionalmente los endpoints de la API.

Evidencia:

- `tests/PanamaAlert.postman_collection.json`

### 5.10 Pruebas JMeter

Se incluye un plan de pruebas JMeter para simular usuarios concurrentes y medir rendimiento del API.

Evidencia:

- `tests/PanamaAlert_load.jmx`

La prueba ejecutada sobre `GET /api/incidents` permite medir tiempos promedio, throughput y porcentaje de errores.

## 6. Conclusion de cumplimiento

PanamaAlert cumple los requisitos principales del proyecto porque integra una base de datos MariaDB normalizada, vistas, procedimientos almacenados, API REST, ORM, consultas crudas, Power BI, ETL automatizable, pruebas Postman, pruebas JMeter y un caso de uso completo orientado a un problema real.
