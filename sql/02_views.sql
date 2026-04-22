-- ============================================================================
-- Vistas funcionales y analiticas para PanamaAlert
-- ============================================================================
USE panama_alert;

-- ----------------------------------------------------------------------------
-- 1) v_incidents_full
--    Vista operativa + analitica base. Mantiene las columnas usadas por la app
--    y suma columnas derivadas listas para Power BI / Tableau.
-- ----------------------------------------------------------------------------
DROP VIEW IF EXISTS v_incidents_full;
CREATE VIEW v_incidents_full AS
SELECT
    i.id                 AS incident_id,
    i.title,
    i.description,
    i.lat,
    i.lng,
    i.severity,
    i.status,
    i.created_at,
    i.updated_at,
    i.verified_at,
    c.id                 AS category_id,
    c.name               AS category_name,
    c.icon               AS category_icon,
    c.color_hex          AS category_color,
    u.id                 AS reporter_id,
    u.username           AS reporter_username,
    u.full_name          AS reporter_name,
    d.id                 AS district_id,
    d.name               AS district_name,
    p.id                 AS province_id,
    p.name               AS province_name,
    COALESCE(vs.up_votes, 0)        AS up_votes,
    COALESCE(vs.down_votes, 0)      AS down_votes,
    COALESCE(vs.score, 0)           AS score,
    COALESCE(cc.comments_count, 0)  AS comments_count,

    DATE(i.created_at)              AS incident_date,
    TIME(i.created_at)              AS incident_time,
    YEAR(i.created_at)              AS incident_year,
    QUARTER(i.created_at)           AS incident_quarter,
    MONTH(i.created_at)             AS incident_month,
    DAY(i.created_at)               AS incident_day,
    HOUR(i.created_at)              AS incident_hour,
    WEEK(i.created_at, 3)           AS incident_week_iso,
    CASE MONTH(i.created_at)
        WHEN 1 THEN 'Enero'
        WHEN 2 THEN 'Febrero'
        WHEN 3 THEN 'Marzo'
        WHEN 4 THEN 'Abril'
        WHEN 5 THEN 'Mayo'
        WHEN 6 THEN 'Junio'
        WHEN 7 THEN 'Julio'
        WHEN 8 THEN 'Agosto'
        WHEN 9 THEN 'Septiembre'
        WHEN 10 THEN 'Octubre'
        WHEN 11 THEN 'Noviembre'
        WHEN 12 THEN 'Diciembre'
        ELSE ''
    END AS incident_month_name,
    CASE DAYOFWEEK(i.created_at)
        WHEN 1 THEN 'Domingo'
        WHEN 2 THEN 'Lunes'
        WHEN 3 THEN 'Martes'
        WHEN 4 THEN 'Miercoles'
        WHEN 5 THEN 'Jueves'
        WHEN 6 THEN 'Viernes'
        WHEN 7 THEN 'Sabado'
        ELSE ''
    END AS incident_day_name,
    CASE i.severity
        WHEN 1 THEN 'Baja'
        WHEN 2 THEN 'Media'
        WHEN 3 THEN 'Alta'
        WHEN 4 THEN 'Critica'
        WHEN 5 THEN 'Extrema'
        ELSE 'Sin clasificar'
    END AS severity_label,
    CASE
        WHEN i.severity >= 4 THEN 'Alta criticidad'
        WHEN i.severity = 3 THEN 'Media criticidad'
        ELSE 'Baja criticidad'
    END AS severity_band,
    CASE i.status
        WHEN 'pending' THEN 'Pendiente'
        WHEN 'verified' THEN 'Verificado'
        WHEN 'resolved' THEN 'Resuelto'
        WHEN 'dismissed' THEN 'Descartado'
        ELSE i.status
    END AS status_label,
    CASE WHEN i.status = 'verified' THEN 1 ELSE 0 END AS is_verified,
    CASE WHEN i.status = 'pending' THEN 1 ELSE 0 END AS is_pending,
    CASE WHEN i.status = 'resolved' THEN 1 ELSE 0 END AS is_resolved,
    CASE WHEN i.status = 'dismissed' THEN 1 ELSE 0 END AS is_dismissed,
    CASE
        WHEN u.username = 'newsbot' OR i.description LIKE '%[Fuente externa:%'
            THEN 'Bot / Fuente externa'
        ELSE 'Reporte ciudadano'
    END AS source_type,
    CONCAT(CAST(i.lat AS CHAR), ',', CAST(i.lng AS CHAR)) AS geo_point,
    TIMESTAMPDIFF(MINUTE, i.created_at, i.verified_at) AS verification_minutes
FROM incidents i
JOIN incident_categories c ON c.id = i.category_id
JOIN users u               ON u.id = i.user_id
LEFT JOIN districts d      ON d.id = i.district_id
LEFT JOIN provinces p      ON p.id = d.province_id
LEFT JOIN (
    SELECT
        incident_id,
        SUM(CASE WHEN vote = 1 THEN 1 ELSE 0 END) AS up_votes,
        SUM(CASE WHEN vote = -1 THEN 1 ELSE 0 END) AS down_votes,
        SUM(vote) AS score
    FROM incident_votes
    GROUP BY incident_id
) vs ON vs.incident_id = i.id
LEFT JOIN (
    SELECT incident_id, COUNT(*) AS comments_count
    FROM incident_comments
    GROUP BY incident_id
) cc ON cc.incident_id = i.id;

-- ----------------------------------------------------------------------------
-- 2) v_incidents_daily_stats
--    Serie diaria agregada por provincia / distrito / categoria.
-- ----------------------------------------------------------------------------
DROP VIEW IF EXISTS v_incidents_daily_stats;
CREATE VIEW v_incidents_daily_stats AS
SELECT
    DATE(i.created_at)            AS day,
    YEAR(i.created_at)            AS year,
    MONTH(i.created_at)           AS month,
    DAY(i.created_at)             AS day_of_month,
    WEEK(i.created_at, 3)         AS iso_week,
    CASE MONTH(i.created_at)
        WHEN 1 THEN 'Enero'
        WHEN 2 THEN 'Febrero'
        WHEN 3 THEN 'Marzo'
        WHEN 4 THEN 'Abril'
        WHEN 5 THEN 'Mayo'
        WHEN 6 THEN 'Junio'
        WHEN 7 THEN 'Julio'
        WHEN 8 THEN 'Agosto'
        WHEN 9 THEN 'Septiembre'
        WHEN 10 THEN 'Octubre'
        WHEN 11 THEN 'Noviembre'
        WHEN 12 THEN 'Diciembre'
        ELSE ''
    END AS month_name,
    CASE DAYOFWEEK(i.created_at)
        WHEN 1 THEN 'Domingo'
        WHEN 2 THEN 'Lunes'
        WHEN 3 THEN 'Martes'
        WHEN 4 THEN 'Miercoles'
        WHEN 5 THEN 'Jueves'
        WHEN 6 THEN 'Viernes'
        WHEN 7 THEN 'Sabado'
        ELSE ''
    END AS day_name,
    p.name                        AS province,
    d.name                        AS district,
    c.name                        AS category,
    COUNT(*)                      AS total_incidents,
    SUM(CASE WHEN i.status='verified' THEN 1 ELSE 0 END) AS verified_count,
    SUM(CASE WHEN i.status='pending' THEN 1 ELSE 0 END) AS pending_count,
    SUM(CASE WHEN i.status='resolved' THEN 1 ELSE 0 END) AS resolved_count,
    SUM(CASE WHEN i.status='dismissed' THEN 1 ELSE 0 END) AS dismissed_count,
    ROUND(AVG(i.severity), 2)     AS avg_severity,
    MAX(i.severity)               AS max_severity,
    ROUND(
        100 * SUM(CASE WHEN i.status='verified' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0),
        2
    ) AS verification_rate,
    CASE
        WHEN AVG(i.severity) >= 4 THEN 'Alta criticidad'
        WHEN AVG(i.severity) >= 3 THEN 'Media criticidad'
        ELSE 'Baja criticidad'
    END AS severity_band
FROM incidents i
JOIN incident_categories c ON c.id = i.category_id
LEFT JOIN districts d      ON d.id = i.district_id
LEFT JOIN provinces p      ON p.id = d.province_id
GROUP BY
    DATE(i.created_at),
    YEAR(i.created_at),
    MONTH(i.created_at),
    DAY(i.created_at),
    WEEK(i.created_at, 3),
    CASE MONTH(i.created_at)
        WHEN 1 THEN 'Enero'
        WHEN 2 THEN 'Febrero'
        WHEN 3 THEN 'Marzo'
        WHEN 4 THEN 'Abril'
        WHEN 5 THEN 'Mayo'
        WHEN 6 THEN 'Junio'
        WHEN 7 THEN 'Julio'
        WHEN 8 THEN 'Agosto'
        WHEN 9 THEN 'Septiembre'
        WHEN 10 THEN 'Octubre'
        WHEN 11 THEN 'Noviembre'
        WHEN 12 THEN 'Diciembre'
        ELSE ''
    END,
    CASE DAYOFWEEK(i.created_at)
        WHEN 1 THEN 'Domingo'
        WHEN 2 THEN 'Lunes'
        WHEN 3 THEN 'Martes'
        WHEN 4 THEN 'Miercoles'
        WHEN 5 THEN 'Jueves'
        WHEN 6 THEN 'Viernes'
        WHEN 7 THEN 'Sabado'
        ELSE ''
    END,
    p.name, d.name, c.name;

-- ----------------------------------------------------------------------------
-- 3) v_user_activity
--    Actividad por usuario con campos derivados listos para BI.
-- ----------------------------------------------------------------------------
DROP VIEW IF EXISTS v_user_activity;
CREATE VIEW v_user_activity AS
SELECT
    u.id                         AS user_id,
    u.username,
    u.full_name,
    u.email,
    r.name                       AS role,
    COALESCE(pl.name, 'Free')    AS current_plan,
    COALESCE(pl.price_monthly_usd, 0.00) AS price_monthly_usd,
    COUNT(DISTINCT i.id)         AS incidents_reported,
    SUM(CASE WHEN i.status='verified' THEN 1 ELSE 0 END) AS verified_reports,
    MAX(i.created_at)            AS last_report_at,
    u.last_login_at,
    u.created_at                 AS joined_at,
    YEAR(u.created_at)           AS joined_year,
    MONTH(u.created_at)          AS joined_month,
    CASE MONTH(u.created_at)
        WHEN 1 THEN 'Enero'
        WHEN 2 THEN 'Febrero'
        WHEN 3 THEN 'Marzo'
        WHEN 4 THEN 'Abril'
        WHEN 5 THEN 'Mayo'
        WHEN 6 THEN 'Junio'
        WHEN 7 THEN 'Julio'
        WHEN 8 THEN 'Agosto'
        WHEN 9 THEN 'Septiembre'
        WHEN 10 THEN 'Octubre'
        WHEN 11 THEN 'Noviembre'
        WHEN 12 THEN 'Diciembre'
        ELSE ''
    END AS joined_month_name,
    ROUND(
        100 * SUM(CASE WHEN i.status='verified' THEN 1 ELSE 0 END) / NULLIF(COUNT(DISTINCT i.id), 0),
        2
    ) AS verification_rate,
    CASE
        WHEN LOWER(COALESCE(pl.name, 'free')) IN ('free', 'none', '') THEN 0
        ELSE 1
    END AS has_paid_plan
FROM users u
JOIN roles r              ON r.id = u.role_id
LEFT JOIN subscriptions s ON s.user_id = u.id AND s.status = 'active'
LEFT JOIN plans pl        ON pl.id = s.plan_id
LEFT JOIN incidents i     ON i.user_id = u.id
GROUP BY
    u.id, u.username, u.full_name, u.email, r.name,
    pl.name, pl.price_monthly_usd,
    u.last_login_at, u.created_at;

-- ----------------------------------------------------------------------------
-- 4) v_hotspots
--    Agregado geografico para mapa de calor y bubble map.
-- ----------------------------------------------------------------------------
DROP VIEW IF EXISTS v_hotspots;
CREATE VIEW v_hotspots AS
SELECT
    ROUND(lat, 2)                AS lat_cell,
    ROUND(lng, 2)                AS lng_cell,
    CONCAT(CAST(ROUND(lat, 2) AS CHAR), ',', CAST(ROUND(lng, 2) AS CHAR)) AS geo_point,
    COUNT(*)                     AS incidents_30d,
    SUM(CASE WHEN status='verified' THEN 1 ELSE 0 END) AS verified_30d,
    SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending_30d,
    ROUND(AVG(severity), 2)      AS avg_severity,
    CASE
        WHEN AVG(severity) >= 4 THEN 'Alta criticidad'
        WHEN AVG(severity) >= 3 THEN 'Media criticidad'
        ELSE 'Baja criticidad'
    END AS severity_band,
    MAX(created_at)              AS last_incident_at,
    DATE(MAX(created_at))        AS last_incident_date
FROM incidents
WHERE created_at >= (NOW() - INTERVAL 30 DAY)
GROUP BY ROUND(lat, 2), ROUND(lng, 2);

-- ----------------------------------------------------------------------------
-- 5) v_bi_overview_kpis
--    Vista tipo metric/value para cards KPI y resumen ejecutivo.
-- ----------------------------------------------------------------------------
DROP VIEW IF EXISTS v_bi_overview_kpis;
CREATE VIEW v_bi_overview_kpis AS
SELECT 1 AS sort_order, 'Total incidentes' AS metric, CAST(COUNT(*) AS DECIMAL(18,2)) AS metric_value
FROM incidents
UNION ALL
SELECT 2, 'Incidentes verificados', CAST(SUM(CASE WHEN status='verified' THEN 1 ELSE 0 END) AS DECIMAL(18,2))
FROM incidents
UNION ALL
SELECT 3, 'Incidentes pendientes', CAST(SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS DECIMAL(18,2))
FROM incidents
UNION ALL
SELECT 4, 'Incidentes descartados', CAST(SUM(CASE WHEN status='dismissed' THEN 1 ELSE 0 END) AS DECIMAL(18,2))
FROM incidents
UNION ALL
SELECT 5, 'Severidad promedio', CAST(ROUND(AVG(severity), 2) AS DECIMAL(18,2))
FROM incidents
UNION ALL
SELECT 6, 'Usuarios registrados', CAST(COUNT(*) AS DECIMAL(18,2))
FROM users
UNION ALL
SELECT 7, 'Usuarios con plan pago',
       CAST(SUM(CASE WHEN LOWER(COALESCE(pl.name, 'free')) IN ('free', 'none', '') THEN 0 ELSE 1 END) AS DECIMAL(18,2))
FROM users u
LEFT JOIN subscriptions s ON s.user_id = u.id AND s.status = 'active'
LEFT JOIN plans pl ON pl.id = s.plan_id;

-- ----------------------------------------------------------------------------
-- 6) v_bi_category_summary
--    Resumen por categoria para donut / barras / treemap.
-- ----------------------------------------------------------------------------
DROP VIEW IF EXISTS v_bi_category_summary;
CREATE VIEW v_bi_category_summary AS
SELECT
    c.id                         AS category_id,
    c.name                       AS category_name,
    c.icon                       AS category_icon,
    c.color_hex                  AS category_color,
    COUNT(i.id)                  AS total_incidents,
    SUM(CASE WHEN i.status='verified' THEN 1 ELSE 0 END) AS verified_incidents,
    SUM(CASE WHEN i.status='pending' THEN 1 ELSE 0 END) AS pending_incidents,
    SUM(CASE WHEN i.status='dismissed' THEN 1 ELSE 0 END) AS dismissed_incidents,
    ROUND(AVG(i.severity), 2)    AS avg_severity,
    MAX(i.created_at)            AS last_incident_at
FROM incident_categories c
LEFT JOIN incidents i ON i.category_id = c.id
GROUP BY c.id, c.name, c.icon, c.color_hex;

