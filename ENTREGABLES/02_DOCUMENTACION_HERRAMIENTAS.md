# Documentacion de Herramientas Utilizadas

## 1. MariaDB

MariaDB se utilizo como sistema gestor de base de datos relacional. En este proyecto almacena usuarios, roles, incidentes, categorias, ubicaciones, votos, comentarios, sesiones, auditoria, preferencias, datos de ETL y elementos necesarios para Power BI.

Uso dentro del proyecto:

- Creacion del esquema relacional.
- Definicion de llaves primarias y foraneas.
- Implementacion de vistas funcionales.
- Implementacion de procedimientos almacenados.
- Almacenamiento central para la app y Power BI.

Archivos relacionados:

- `sql/01_schema.sql`
- `sql/02_views.sql`
- `sql/03_procedures.sql`
- `sql/04_triggers.sql`
- `sql/05_seed.sql`

## 2. Flask

Flask se utilizo como framework backend de la aplicacion web. Permite crear rutas web, endpoints API, manejo de sesiones, autenticacion y comunicacion con la base de datos.

Uso dentro del proyecto:

- Rutas principales de la aplicacion.
- API REST.
- Login, registro y seguridad.
- Integracion con SQLAlchemy.
- Respuestas JSON para frontend y pruebas.

Archivos relacionados:

- `run.py`
- `app/__init__.py`
- `app/main/routes.py`
- `app/api/routes.py`
- `app/auth/routes.py`

## 3. SQLAlchemy ORM

SQLAlchemy se utilizo como ORM para representar tablas de MariaDB mediante clases Python. Esto permite manejar datos de forma estructurada desde el backend.

Uso dentro del proyecto:

- Modelos para usuarios, incidentes, categorias, comentarios, votos y sesiones.
- Consultas ORM para operaciones comunes.
- Integracion con Flask-Migrate.

Archivos relacionados:

- `app/models.py`
- `app/extensions.py`

## 4. Consultas SQL crudas

Ademas del ORM, se usaron consultas SQL crudas para operaciones avanzadas como reportes, estadisticas, vistas, procedimientos y validaciones especiales.

Uso dentro del proyecto:

- Consultas de dashboard.
- Consumo de vistas.
- Operaciones de seguridad.
- Logica avanzada que es mas eficiente directamente en SQL.

Archivos relacionados:

- `app/main/routes.py`
- `app/api/routes.py`
- `app/services/trust.py`

## 5. HTML, CSS y JavaScript

El frontend se desarrollo usando plantillas HTML, CSS y JavaScript. Permite renderizar login, registro, mapa, dashboard, perfil, asistente y vistas administrativas.

Uso dentro del proyecto:

- Interfaz del usuario.
- Mapa interactivo.
- Modales para crear incidentes.
- Perfil y preferencias.
- Integracion con API REST mediante `fetch`.

Archivos relacionados:

- `template/login.html`
- `template/registro.html`
- `template/mapa.html`
- `template/dashboard.html`
- `template/profile.html`
- `template/assistant.html`
- `static/styles.css`
- `static/mapa.js`

## 6. Leaflet

Leaflet se utilizo para construir el mapa interactivo de PanamaAlert.

Uso dentro del proyecto:

- Mostrar mapa de Panama.
- Colocar pines de incidentes y ofertas.
- Abrir popups con informacion.
- Enlazar ubicaciones con Google Maps.
- Permitir interaccion del usuario con el mapa.

Archivo relacionado:

- `static/mapa.js`

## 7. Power BI

Power BI se utilizo para crear un dashboard administrativo conectado a la base de datos MariaDB mediante ODBC.

Uso dentro del proyecto:

- Visualizar KPIs.
- Analizar incidentes por categoria.
- Ver tendencias por fecha.
- Crear mapa de incidentes y hotspots.
- Consultar actividad de usuarios.

Vistas usadas:

- `v_bi_overview_kpis`
- `v_bi_category_summary`
- `v_incidents_full`
- `v_incidents_daily_stats`
- `v_hotspots`
- `v_user_activity`

Archivos relacionados:

- `bi/powerbi_connection.md`
- `bi/powerbi_dashboard_layout.md`
- `bi/powerbi_measures.dax`

## 8. ODBC MySQL/MariaDB

ODBC se uso como puente entre Power BI Desktop y MariaDB en la VM.

Uso dentro del proyecto:

- Crear DSN hacia la base `panama_alert`.
- Conectar Power BI sin depender del conector web.
- Leer vistas directamente desde MariaDB.

Configuracion utilizada:

- Servidor: IP de la VM.
- Puerto: `3306`.
- Base de datos: `panama_alert`.
- Usuario BI: `bi_reader`.

## 9. Postman

Postman se utilizo para pruebas funcionales de la API REST.

Uso dentro del proyecto:

- Importar coleccion.
- Ejecutar endpoints.
- Validar respuestas JSON.
- Verificar funcionamiento de rutas GET, POST, PUT y DELETE.

Archivo relacionado:

- `tests/PanamaAlert.postman_collection.json`

## 10. Apache JMeter

JMeter se utilizo para pruebas de carga y rendimiento.

Uso dentro del proyecto:

- Simular usuarios concurrentes.
- Ejecutar peticiones al API.
- Medir tiempo promedio, minimo, maximo, throughput y porcentaje de errores.
- Generar evidencia de rendimiento.

Archivo relacionado:

- `tests/PanamaAlert_load.jmx`

## 11. Gunicorn

Gunicorn se uso como servidor WSGI para ejecutar Flask en modo produccion.

Uso dentro del proyecto:

- Levantar la app con multiples workers.
- Manejar concurrencia.
- Ejecutar la aplicacion como servicio en Oracle Linux 8.

Archivos relacionados:

- `gunicorn.conf.py`
- `start_prod.sh`

## 12. systemd

systemd se uso para ejecutar PanamaAlert como servicio en la VM.

Uso dentro del proyecto:

- Iniciar la app automaticamente.
- Reiniciar si falla.
- Consultar estado con `systemctl status`.
- Revisar logs con `journalctl`.

Archivo relacionado:

- `docs/panamaalert.service.example`

## 13. Nginx

Nginx se uso como reverse proxy delante de Gunicorn.

Uso dentro del proyecto:

- Recibir trafico HTTP.
- Redirigir solicitudes hacia Gunicorn.
- Servir archivos estaticos.
- Preparar la app para HTTPS.

Archivo relacionado:

- `docs/nginx.panamaalert.conf.example`

## 14. OpenAI API

La API de OpenAI se integro para funciones de asistente, analisis, resumen y enriquecimiento de informacion.

Uso dentro del proyecto:

- Mejorar respuestas del asistente.
- Analizar zonas.
- Generar resumenes.
- Apoyar mensajes del bot.

Archivos relacionados:

- `app/ai_service.py`
- `app/services/news_ingest.py`

## 15. SMTP Gmail

SMTP se uso para enviar correos reales desde una cuenta de notificacion de PanamaAlert.

Uso dentro del proyecto:

- Enviar resumenes a usuarios que aceptan notificaciones por correo.
- Permitir correo de prueba desde perfil.

Archivos relacionados:

- `app/services/mailer.py`
- `.env`
