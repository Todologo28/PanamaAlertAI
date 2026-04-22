# PanamaAlert - Layout rapido para Power BI

## Pagina 1: Resumen Administrativo

Usa visuales tipo `Tarjeta`.

- `Total Incidentes`
- `Incidentes Verificados`
- `Incidentes Pendientes`
- `Severidad Promedio`
- `Incidentes 24h`
- `Pings Bot`

Usa visual `Grafico de lineas`.

- Eje X: `v_incidents_daily_stats[day]`
- Valores: `v_incidents_daily_stats[total_incidents]`
- Leyenda opcional: `v_incidents_daily_stats[category]`

Usa visual `Barras`.

- Eje: `v_bi_category_summary[category_name]`
- Valores: `v_bi_category_summary[total_incidents]`

## Pagina 2: Mapa de Alertas

Usa visual `Mapa`.

- Latitud: `v_incidents_full[lat]`
- Longitud: `v_incidents_full[lng]`
- Leyenda: `v_incidents_full[category_name]`
- Tamano: `v_incidents_full[severity]`
- Tooltips: `title`, `status_label`, `severity_label`, `source_type`, `created_at`

Slicers recomendados:

- `v_incidents_full[status_label]`
- `v_incidents_full[category_name]`
- `v_incidents_full[source_type]`
- `v_incidents_full[incident_date]`

## Pagina 3: Hotspots

Usa visual `Mapa` o `Azure Maps`.

- Latitud: `v_hotspots[lat_cell]`
- Longitud: `v_hotspots[lng_cell]`
- Tamano: `v_hotspots[incidents_30d]`
- Color/Leyenda: `v_hotspots[severity_band]`
- Tooltips: `avg_severity`, `verified_30d`, `pending_30d`, `last_incident_at`

Usa visual `Tabla`.

- `lat_cell`
- `lng_cell`
- `incidents_30d`
- `avg_severity`
- `severity_band`
- `last_incident_date`

## Pagina 4: Usuarios y Productividad

Usa visual `Tarjeta`.

- `Usuarios Registrados`
- `Usuarios Pago`
- `Tasa Usuarios Pago`

Usa visual `Barras`.

- Eje: `v_user_activity[username]`
- Valores: `v_user_activity[incidents_reported]`

Usa visual `Tabla`.

- `username`
- `role`
- `current_plan`
- `incidents_reported`
- `verified_reports`
- `verification_rate`
- `last_report_at`

## Reglas importantes

- No uses `Suma de incident_id`.
- Usa medidas DAX para KPIs.
- Para conteos rapidos usa `Recuento de incident_id` o `Total Incidentes`.
- Para la demo, no necesitas relacionar todas las tablas tecnicas.
- Oculta tablas tecnicas como `active_sessions`, `auth_attempts`, `audit_log`, `api_keys`, `etl_runs`.

