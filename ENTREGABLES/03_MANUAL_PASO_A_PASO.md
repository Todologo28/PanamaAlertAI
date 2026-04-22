# Manual Paso a Paso

## 1. Requisitos previos

Antes de instalar PanamaAlert se necesita:

- Oracle Linux 8 o una distribucion Linux compatible.
- Python 3.11.
- MariaDB Server.
- Acceso a terminal.
- Power BI Desktop en Windows.
- Postman.
- Apache JMeter.
- Conector ODBC MySQL/MariaDB para Power BI.

## 2. Descomprimir el proyecto

En la VM:

```bash
cd /home/egonzalez/Documents/app
unzip PanamaAlert2.zip
cd PanamaAlert2
```

Validar que existan carpetas como:

```text
app
sql
etl
bi
tests
template
static
```

## 3. Crear entorno Python

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Configurar variables de entorno

Crear archivo `.env`:

```bash
cp .env.example .env
vi .env
```

Variables importantes:

```text
SECRET_KEY
JWT_SECRET
DB_HOST
DB_PORT
DB_USER
DB_PASS
DB_NAME
TOTP_ENC_KEY
OPENAI_API_KEY
MAIL_ENABLED
MAIL_HOST
MAIL_PORT
MAIL_USERNAME
MAIL_PASSWORD
MAIL_FROM
```

## 5. Crear base de datos

Entrar a MariaDB:

```bash
sudo mysql
```

Crear usuario si hace falta:

```sql
CREATE USER IF NOT EXISTS 'panama_alert'@'%' IDENTIFIED BY 'panama_alert';
GRANT ALL PRIVILEGES ON panama_alert.* TO 'panama_alert'@'%';
FLUSH PRIVILEGES;
```

Ejecutar scripts:

```bash
cd /home/egonzalez/Documents/app/PanamaAlert2
mysql -u root -p < sql/00_run_all.sql
```

Para actualizar solo vistas sin borrar datos:

```bash
mysql -u root -p panama_alert < sql/02_views.sql
```

## 6. Ejecutar la aplicacion en desarrollo

```bash
source .venv/bin/activate
python run.py
```

Abrir en navegador:

```text
http://IP_DE_LA_VM:5000
```

## 7. Ejecutar la aplicacion en produccion

Dar permiso al script:

```bash
chmod +x start_prod.sh
```

Crear servicio systemd:

```bash
sudo vi /etc/systemd/system/panamaalert.service
```

Ejemplo:

```ini
[Unit]
Description=PanamaAlert Gunicorn Service
After=network.target

[Service]
Type=simple
User=egonzalez
Group=egonzalez
WorkingDirectory=/home/egonzalez/Documents/app/PanamaAlert2
Environment=PORT=5000
ExecStart=/usr/bin/bash /home/egonzalez/Documents/app/PanamaAlert2/start_prod.sh
Restart=always
RestartSec=5
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
```

Activar:

```bash
sudo systemctl daemon-reload
sudo systemctl enable panamaalert
sudo systemctl restart panamaalert
sudo systemctl status panamaalert
```

Ver logs:

```bash
sudo journalctl -u panamaalert -n 80 --no-pager
```

## 8. Probar salud del sistema

```bash
curl http://127.0.0.1:5000/health
```

Respuesta esperada:

```json
{
  "status": "ok",
  "db": "up",
  "ai": "up"
}
```

## 9. Usar la app

Flujo basico:

1. Entrar a la pagina principal.
2. Ver mapa publico.
3. Iniciar sesion.
4. Reportar incidente desde el mapa.
5. Consultar alerta en sidebar.
6. Abrir popup del ping.
7. Usar perfil para preferencias.
8. Probar envio de resumen si SMTP esta configurado.
9. Consultar dashboard interno.
10. Usar asistente IA.

## 10. Ejecutar ETL

Ejecutar manualmente:

```bash
source .venv/bin/activate
python etl/etl_pipeline.py
```

El bot de fuentes externas se apoya en:

```text
app/services/news_ingest.py
app_data/news/sources.json
```

Proceso del ETL:

1. Extraer datos desde fuentes configuradas.
2. Limpiar HTML/texto.
3. Detectar si el contenido es relevante.
4. Identificar comercio, zona o direccion.
5. Resolver ubicacion.
6. Crear ping/incidente.
7. Registrar ejecucion.

## 11. Conectar Power BI

1. Instalar conector ODBC MySQL/MariaDB en Windows.
2. Crear DSN llamado `panama_alert`.
3. Usar servidor IP de la VM.
4. Puerto `3306`.
5. Usuario `bi_reader`.
6. Base `panama_alert`.
7. En Power BI seleccionar `Obtener datos > ODBC`.
8. Cargar vistas:

```text
v_bi_overview_kpis
v_bi_category_summary
v_incidents_full
v_incidents_daily_stats
v_hotspots
v_user_activity
```

## 12. Crear dashboard Power BI

Pagina 1: Resumen Administrativo.

- Tarjetas desde `v_bi_overview_kpis`.
- Barras por categoria desde `v_bi_category_summary`.
- Linea diaria desde `v_incidents_daily_stats`.

Pagina 2: Mapa de Alertas.

- Latitud: `lat`.
- Longitud: `lng`.
- Categoria: `category_name`.
- Detalles: `title`, `status_label`, `severity_label`.

Pagina 3: Hotspots.

- Latitud: `lat_cell`.
- Longitud: `lng_cell`.
- Tamano: `incidents_30d`.

Pagina 4: Usuarios.

- Tabla desde `v_user_activity`.

## 13. Ejecutar Postman

1. Abrir Postman.
2. Importar:

```text
tests/PanamaAlert.postman_collection.json
```

3. Configurar `base_url`:

```text
http://IP_DE_LA_VM:5000
```

4. Ejecutar coleccion.
5. Guardar capturas como evidencia.

## 14. Ejecutar JMeter

1. Abrir Apache JMeter.
2. Abrir:

```text
tests/PanamaAlert_load.jmx
```

3. Configurar HOST y PORT.
4. Usar endpoint publico:

```text
/api/incidents?limit=50
```

5. Ejecutar prueba.
6. Revisar:

```text
Summary Report
Aggregate Report
View Results Tree
```

7. Guardar capturas.

## 15. Evidencias finales

Para la entrega se deben incluir:

- Diagrama ER.
- Capturas de la app.
- Capturas del dashboard Power BI.
- Capturas de Postman.
- Capturas de JMeter.
- Scripts SQL.
- Codigo fuente.
- Documentacion de esta carpeta.
