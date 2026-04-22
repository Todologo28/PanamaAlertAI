# Conexion Power BI a MariaDB (PanamaAlert)

## 1. Pre-requisitos en la VM OL8
```bash
sudo dnf install -y mariadb-server
sudo systemctl enable --now mariadb
sudo mysql_secure_installation

sudo mysql -e "
CREATE USER IF NOT EXISTS 'bi_reader'@'%' IDENTIFIED BY 'BiReader_2026!';
GRANT SELECT ON panama_alert.* TO 'bi_reader'@'%';
FLUSH PRIVILEGES;"

sudo sed -i 's/^bind-address.*/bind-address = 0.0.0.0/' /etc/my.cnf.d/mariadb-server.cnf
sudo systemctl restart mariadb
sudo firewall-cmd --permanent --add-port=3306/tcp
sudo firewall-cmd --reload
```

## 2. Conexion desde Power BI Desktop
Ruta recomendada:
1. `Obtener datos -> ODBC`
2. Crear o seleccionar un DSN hacia MariaDB
3. Servidor: `IP_DE_TU_VM`
4. Puerto: `3306`
5. Base de datos: `panama_alert`
6. Usuario: `bi_reader`
7. Clave: la del usuario BI

Ruta alternativa:
1. `Obtener datos -> MySQL Database`
2. Si el conector MySQL falla en Windows, vuelve a ODBC: suele ser mas estable con MariaDB

Modo recomendado:
- `Import` para una demo estable
- `DirectQuery` si quieres reflejo mas cercano a tiempo real

## 3. Vistas SQL recomendadas
Importa estas primero:
- `v_incidents_full`
- `v_incidents_daily_stats`
- `v_hotspots`
- `v_user_activity`
- `v_bi_overview_kpis`
- `v_bi_category_summary`

Opcionales:
- `incident_categories`
- `districts`
- `provinces`
- `plans`

## 4. Que usar para cada visual
| Vista | Para que sirve |
|------|------|
| `v_incidents_full` | mapa, tabla detalle, slicers por estado, severidad, categoria, fecha, fuente |
| `v_incidents_daily_stats` | line chart, stacked bars, comparacion por provincia/distrito/categoria |
| `v_hotspots` | heatmap, bubble map, ranking de zonas |
| `v_user_activity` | productividad, planes, usuarios mas activos, tasa de verificacion |
| `v_bi_overview_kpis` | tarjetas KPI |
| `v_bi_category_summary` | donut, barras, treemap por categoria |

## 5. Campos que ya salen listos
### `v_incidents_full`
- `incident_date`
- `incident_time`
- `incident_year`
- `incident_quarter`
- `incident_month`
- `incident_day`
- `incident_hour`
- `incident_week_iso`
- `incident_month_name`
- `incident_day_name`
- `severity_label`
- `severity_band`
- `status_label`
- `is_verified`
- `is_pending`
- `is_resolved`
- `is_dismissed`
- `geo_point`
- `source_type`
- `verification_minutes`

### `v_incidents_daily_stats`
- `year`
- `month`
- `day_of_month`
- `iso_week`
- `month_name`
- `day_name`
- `pending_count`
- `dismissed_count`
- `verification_rate`
- `severity_band`

### `v_hotspots`
- `geo_point`
- `verified_30d`
- `pending_30d`
- `severity_band`
- `last_incident_date`

### `v_user_activity`
- `joined_year`
- `joined_month`
- `joined_month_name`
- `verification_rate`
- `has_paid_plan`

### `v_bi_overview_kpis`
- `sort_order`
- `metric`
- `metric_value`

### `v_bi_category_summary`
- `total_incidents`
- `verified_incidents`
- `pending_incidents`
- `dismissed_incidents`
- `avg_severity`
- `last_incident_at`

## 6. Modelo sugerido
Para una demo rapida:
- puedes cargar solo las vistas y trabajar sin relaciones complejas

Para un modelo mas limpio:
- `v_incidents_full[category_id]` -> `incident_categories[id]`
- `v_incidents_full[district_id]` -> `districts[id]`
- `districts[province_id]` -> `provinces[id]`

Recomendaciones:
- deja `v_bi_overview_kpis` aislada para cards
- deja `v_hotspots` aislada si solo la usaras para mapa de calor

## 7. Paginas sugeridas del tablero
| Pagina | Vistas principales | Visuales |
|------|------|------|
| Vista General | `v_bi_overview_kpis`, `v_incidents_daily_stats`, `v_bi_category_summary` | KPIs, linea diaria, top categorias |
| Mapa | `v_incidents_full` | map con `lat`, `lng`, color por categoria, tamano por severidad |
| Hotspots | `v_hotspots` | heatmap o bubble map |
| Productividad | `v_user_activity` | tabla, barras por plan, ranking reportantes |
| Moderacion | `v_incidents_full` | funnel por estado y detalle de pendientes |

## 8. Medidas DAX recomendadas
```DAX
Incidentes 24h =
CALCULATE(
  COUNTROWS(v_incidents_full),
  v_incidents_full[created_at] >= NOW() - 1
)

Tasa Verificacion =
DIVIDE(
  CALCULATE(COUNTROWS(v_incidents_full), v_incidents_full[status] = "verified"),
  COUNTROWS(v_incidents_full)
)

Usuarios Pago =
CALCULATE(
  COUNTROWS(v_user_activity),
  v_user_activity[has_paid_plan] = 1
)

Severidad Promedio =
AVERAGE(v_incidents_full[severity])
```

## 9. Flujo rapido para clase
1. Crea el DSN ODBC a MariaDB
2. Importa las 6 vistas recomendadas
3. Haz una pagina `Vista General` con KPIs y tendencia
4. Haz una pagina `Mapa` con `v_incidents_full`
5. Haz una pagina `Hotspots`
6. Haz una pagina `Productividad`

## 10. Alternativa desde la app
Si no quieres DB directa, la app ya expone:
- `/api/bi/export.xlsx`
- `/api/bi/export.csv?dataset=incidents`
- `/api/bi/export.csv?dataset=daily`
- `/api/bi/export.csv?dataset=hotspots`
- `/api/bi/export.csv?dataset=users`
- `/api/bi/export.csv?dataset=overview`
- `/api/bi/manifest`
- `/api/bi/powerquery.pq`

Eso sirve para una demo rapida. Pero si quieres defender que Power BI esta conectado a la base de datos, usa las vistas SQL anteriores.
