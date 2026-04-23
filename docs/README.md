<img width="1205" height="474" alt="image" src="https://github.com/user-attachments/assets/82673cf4-24a8-4ca0-b465-699a2deccfe2" />

# PanamaAlert — Documentación Maestra

Plataforma SaaS para reportar, verificar y visualizar incidentes ciudadanos
(seguridad, tránsito, emergencias) en Panamá. Cubre los 7 requisitos del
proyecto final de Base de Datos II.

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Todologo28/PanamaAlertAI)

## 0. Indice recomendado de entrega

- `docs/README.md`
- `docs/COMPLIANCE_MATRIX.md`
- `docs/MANUAL_PASO_A_PASO.md`
- `docs/GLOSARIO.md`
- `docs/LECCIONES_APRENDIDAS.md`
- `docs/DEPLOY_QUICKSTART.md`
- `bi/powerbi_connection.md`
- `tests/PanamaAlert.postman_collection.json`
- `tests/PanamaAlert_load.jmx`

---

## Screenshot

<img width="1941" height="1082" alt="image" src="https://github.com/user-attachments/assets/c73c131b-eb9a-4888-8be9-080cc7fb6970" />

## 1. Caso de uso

> **Problema:** la información de seguridad ciudadana en Panamá está
> fragmentada (911, redes sociales, medios). Vecinos, periodistas, aseguradoras,
> municipios y empresas necesitan **una sola fuente verificada y geolocalizada
> en tiempo real**.
>
> **Solución:** PanamaAlert Pro recibe reportes ciudadanos georreferenciados,
> los enriquece y verifica vía moderadores, los expone vía mapa, API REST y
> tablero Power BI, y monetiza con planes Free / Pro / Enterprise.

**Actores:** ciudadano, moderador, administrador, integrador (API key).

**Flujos clave:**
1. Ciudadano crea cuenta → 2FA TOTP → reporta incidente con foto y ubicación.
2. SP `sp_create_incident` aplica cuota del plan, registra audit y notifica
   suscriptores cuyas geo-fences cubren el punto (Haversine en SQL).
3. Moderador verifica/rechaza vía `sp_verify_incident`.
4. Periodistas/seguros consumen la API REST con su API key.
5. Power BI conecta directo a las vistas para un tablero municipal en vivo.
6. ETL importa cada 15 min datasets abiertos (datos.gob.pa, feeds RSS) hacia
   `etl_staging_incidents` → `incidents`.

## 2. Estructura del repo

```
PanamaAlert2/
├─ sql/                  # Schema, vistas, SP, triggers, seed (correr en MariaDB)
│  ├─ 00_run_all.sql
│  ├─ 01_schema.sql
│  ├─ 02_views.sql
│  ├─ 03_procedures.sql
│  ├─ 04_triggers.sql
│  └─ 05_seed.sql
├─ app/                  # Flask + SQLAlchemy (ORM)
│  ├─ __init__.py        # factory
│  ├─ config.py
│  ├─ extensions.py
│  ├─ models.py          # ORM 1:1 con schema
│  ├─ security.py        # CSP, CSRF, JWT, TOTP, rate-limit
│  ├─ auth/              # registro, login, 2FA
│  ├─ main/              # rutas web (mapa)
│  └─ api/               # REST v1 (CRUD, raw SQL, SP)
├─ etl/
│  ├─ etl_pipeline.py
│  └─ samples/incidents_sample.csv
├─ bi/powerbi_connection.md
├─ tests/
│  ├─ PanamaAlert.postman_collection.json
│  └─ PanamaAlert_load.jmx
├─ template/, static/    # UI existente (mapa Leaflet)
├─ docs/                 # esta documentación
├─ run.py
├─ requirements.txt
└─ .env.example
```

## 3. Instalación paso a paso (VM OL8 + MariaDB)

### 3.1 Base de datos
```bash
sudo dnf install -y mariadb-server git python3.11 python3.11-pip
sudo systemctl enable --now mariadb

# Crear usuario y cargar schema
sudo mysql <<SQL
CREATE USER 'panama_alert'@'%' IDENTIFIED BY 'panama_alert';
GRANT ALL PRIVILEGES ON panama_alert.* TO 'panama_alert'@'%';
FLUSH PRIVILEGES;
SQL

cd PanamaAlert2/sql
mysql -u root -p < 00_run_all.sql
```

### 3.2 App Flask
```bash
cd PanamaAlert2
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # editar credenciales
export $(cat .env | xargs)
python run.py               # dev
# producción:
gunicorn -w 4 -b 0.0.0.0:5000 'app:create_app()'
```

### 3.3 ETL (cron cada 15 min)
```bash
sudo crontab -e
*/15 * * * * cd /opt/panama_alert && /opt/panama_alert/.venv/bin/python etl/etl_pipeline.py --source etl/samples/incidents_sample.csv >> /var/log/panama_etl.log 2>&1
```

### 3.4 Power BI
Ver `bi/powerbi_connection.md`.

### 3.5 Pruebas
- **Postman:** importar `tests/PanamaAlert.postman_collection.json`,
  ejecutar `Auth → Login` → el resto reutiliza `{{token}}` automáticamente.
- **JMeter:** `jmeter -n -t tests/PanamaAlert_load.jmx -l results.jtl -e -o report/`

## 4. Diagrama Entidad-Relación

<img width="600" height="400" alt="image" src="https://github.com/user-attachments/assets/691f6a3b-ec08-438d-a669-9b3138b4b6e1" />

## 5. Componentes que cumplen el PDF

| Requisito PDF                  | Implementación                                                          |
|--------------------------------|-------------------------------------------------------------------------|
| **DB Relacional 3FN**          | `sql/01_schema.sql`, 17 tablas, sin redundancia transitiva              |
| **2 vistas funcionales**       | 4 vistas: `v_incidents_full`, `v_incidents_daily_stats`, `v_user_activity`, `v_hotspots` |
| **2 stored procedures**        | 5 SP: `sp_create_incident`, `sp_verify_incident`, `sp_nearby_incidents`, `sp_upgrade_plan`, `sp_rate_limit_check` + función `fn_haversine_km` + 3 triggers |
| **API REST + ORM + raw**       | Flask + SQLAlchemy ORM (`models.py`) + raw SQL en `api/routes.py` (vistas + SP) |
| **CRUD RESTful completo**      | Incidents, comments, votes, alert-subs, notifications, plans, dashboard |
| **Visualización BI**           | `bi/powerbi_connection.md` — DirectQuery a vistas                       |
| **ETL automatizado**           | `etl/etl_pipeline.py` + cron + tabla `etl_runs`/`etl_staging_incidents` |
| **Postman + JMeter**           | `tests/`                                                                |
| **Caso de uso integrador**     | Sección 1                                                               |
| **Documentación**              | Este README + manual + ER + glosario + lecciones                        |

## 6. Características que justifican cobrar (innovadoras +5 %)

- **Geo-fences premium** con notificaciones automáticas vía SP + Haversine SQL.
- **Cuotas por plan** validadas en la base de datos (no en la app), inviolables.
- **2FA TOTP** con secret cifrado en reposo (Fernet).
- **API keys hashed** (SHA-256) — la clave nunca se guarda en claro.
- **Audit log + triggers** que registran cualquier mutación de incidentes.
- **Rate limiting persistente en DB** con ventanas deslizantes.
- **CSP con nonce dinámico**, HSTS, SameSite Strict, CSRF doble token.
- **JWT + API keys** coexistiendo (sesión web vs B2B).
- **Vistas de hotspots** listas para Power BI sin transformaciones extra.
- **ETL idempotente con staging** — facilita auditoría y reprocesamiento.

## 7. Glosario

| Término          | Definición                                                          |
|------------------|---------------------------------------------------------------------|
| **3FN**          | Tercera forma normal: sin dependencias transitivas en no-claves    |
| **TOTP**         | Time-based One Time Password (RFC 6238), token 2FA cada 30 s      |
| **JWT**          | JSON Web Token firmado HS256, transporta identidad/rol             |
| **CSP**          | Content Security Policy: cabecera que restringe orígenes de scripts|
| **CSRF**         | Cross-Site Request Forgery, mitigado con token por sesión          |
| **Geo-fence**    | Polígono/círculo geográfico para activar alertas automáticas       |
| **Haversine**    | Fórmula para distancia entre dos puntos en una esfera              |
| **ETL**          | Extract-Transform-Load: pipeline de ingesta hacia el warehouse     |
| **DirectQuery**  | Modo Power BI donde cada visual genera SQL en vivo                 |
| **Rate limiting**| Limitar nº de peticiones/intentos por ventana de tiempo            |
| **Audit log**    | Bitácora inmutable de acciones (compliance / forense)              |
| **Stored Proc**  | Lógica encapsulada en la DB, ejecutable con `CALL`                 |
| **ORM**          | Object Relational Mapper, mapea filas a objetos Python             |

## 8. Lecciones aprendidas

1. **Mover reglas críticas a la base de datos** (cuotas por plan, rate limit,
   notificaciones por geo-fence) las hace inviolables aunque cambies de cliente
   (web, móvil, integrador) — el SP `sp_create_incident` es la prueba.
2. **Vistas como contrato BI**: separar `v_incidents_full` permite cambiar
   tablas internas sin romper Power BI.
3. **Triggers de auditoría** son el camino más barato para compliance;
   evitan tener que recordar auditar desde la app.
4. **Staging en ETL** evita perder datos cuando una transformación falla:
   se reintenta sin volver a llamar la fuente.
5. **JWT + API key** coexistiendo: una para humanos (corta vida), otra para
   máquinas (larga vida, hasheada), modelo industria.
6. **Haversine en SQL** rinde aceptable hasta ~100k filas; pasada esa escala
   conviene índice espacial (`SPATIAL INDEX` MariaDB) o PostGIS.
7. **Rate limiting persistente** (no en memoria) sobrevive a reinicios y
   permite múltiples workers gunicorn sin Redis.
8. **CSP con nonce** elimina inline scripts inseguros sin sacrificar Leaflet.
9. **Migración DynamoDB → MariaDB** reveló cuánto código de "tipos" desaparece
   cuando hay schema fuerte (no más `Decimal()` por todos lados).

## 9. Manual de operación rápida

| Tarea                          | Comando                                                                |
|--------------------------------|------------------------------------------------------------------------|
| Reset DB                       | `mysql -u root -p < sql/00_run_all.sql`                                |
| Levantar app                   | `gunicorn -w 4 -b 0.0.0.0:5000 'app:create_app()'`                     |
| Generar API key (vía Postman)  | `POST /api/v1/auth/api-keys` con Bearer token                          |
| Importar dataset               | `python etl/etl_pipeline.py --source path/al/archivo.csv`              |
| Ver runs ETL                   | `SELECT * FROM etl_runs ORDER BY id DESC LIMIT 20;`                    |
| Ver hotspots                   | `SELECT * FROM v_hotspots ORDER BY incidents_30d DESC LIMIT 10;`       |
| Ascender usuario a moderador   | `UPDATE users SET role_id=(SELECT id FROM roles WHERE name='moderator') WHERE email='x@y';` |
| Carga JMeter                   | `jmeter -n -t tests/PanamaAlert_load.jmx -l out.jtl -e -o report/`     |

## 10. Roadmap (premium)

- Push notifications móviles vía FCM hacia suscriptores de geo-fences.
- Índice espacial nativo (`POINT` + `SPATIAL INDEX`) para consultas O(log n).
- Webhooks salientes para integradores (eventos `incident.verified`).
- Modelo ML de scoring de credibilidad por reportador.
- Modo offline-first en la app web (Service Worker).
