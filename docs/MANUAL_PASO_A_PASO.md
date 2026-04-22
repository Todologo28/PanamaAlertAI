# Manual Paso a Paso

## 1. Preparar base de datos

1. Instalar MariaDB.
2. Crear la base y usuario del proyecto.
3. Ejecutar los scripts de `sql/`.

Orden sugerido:

```bash
mysql -u root -p < sql/00_run_all.sql
```

## 2. Preparar la aplicacion

1. Entrar a la carpeta del proyecto.
2. Crear `.venv`.
3. Instalar dependencias.
4. Configurar `.env`.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 3. Levantar la app

Modo desarrollo:

```bash
python run.py
```

Modo produccion:

```bash
./start_prod.sh
```

## 4. Probar los flujos principales

1. Registrar un usuario.
2. Configurar el token 2FA.
3. Iniciar sesion.
4. Reportar un incidente desde el mapa.
5. Verificar que aparezca en el sidebar y en admin.
6. Corregir o moderar el incidente desde el panel de administracion.

## 5. Probar la API

1. Importar `tests/PanamaAlert.postman_collection.json`.
2. Ejecutar login.
3. Ejecutar CRUD de incidentes.
4. Probar comentarios, votos y consultas de apoyo.

## 6. Probar rendimiento

1. Abrir JMeter.
2. Importar `tests/PanamaAlert_load.jmx`.
3. Ejecutar la prueba.
4. Guardar el reporte generado como evidencia.

## 7. Ejecutar el ETL

```bash
python etl/etl_pipeline.py --source etl/samples/incidents_sample.csv
```

Validar:

- carga en tablas staging
- transformacion
- insercion en tablas del sistema

## 8. Conectar BI

1. Revisar `bi/powerbi_connection.md`.
2. Conectar Power BI a MariaDB.
3. Consumir las vistas del proyecto.
4. Construir visuales de incidentes, tendencia y hotspots.

## 9. Evidencias para la entrega

- capturas del mapa y dashboard
- export del tablero BI
- capturas de Postman
- reporte de JMeter
- scripts SQL
- documentacion en PDF

## 10. Recomendacion para la defensa

Demostrar este orden:

1. Caso de uso
2. DB y modelo relacional
3. API y CRUD
4. ETL
5. BI
6. Pruebas
7. Seguridad y robustez
