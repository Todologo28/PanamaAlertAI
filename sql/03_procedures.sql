-- ============================================================================
-- Procedimientos almacenados + funciones
-- ============================================================================
USE panama_alert;

DELIMITER $$

-- ----------------------------------------------------------------------------
-- Función haversine en km (para alertas geo-cercadas)
-- ----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS fn_haversine_km$$
CREATE FUNCTION fn_haversine_km(lat1 DECIMAL(10,7), lng1 DECIMAL(10,7),
                                lat2 DECIMAL(10,7), lng2 DECIMAL(10,7))
RETURNS DECIMAL(8,3)
DETERMINISTIC
BEGIN
    DECLARE r DECIMAL(8,3);
    SET r = 6371 * 2 * ASIN(SQRT(
        POWER(SIN(RADIANS(lat2 - lat1)/2), 2) +
        COS(RADIANS(lat1)) * COS(RADIANS(lat2)) *
        POWER(SIN(RADIANS(lng2 - lng1)/2), 2)
    ));
    RETURN r;
END$$

-- ----------------------------------------------------------------------------
-- sp_create_incident : crea incidente, audita, notifica suscriptores cercanos
-- ----------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS sp_create_incident$$
CREATE PROCEDURE sp_create_incident(
    IN  p_user_id     INT UNSIGNED,
    IN  p_category_id TINYINT UNSIGNED,
    IN  p_district_id SMALLINT UNSIGNED,
    IN  p_title       VARCHAR(160),
    IN  p_description VARCHAR(1000),
    IN  p_lat         DECIMAL(10,7),
    IN  p_lng         DECIMAL(10,7),
    IN  p_severity    TINYINT UNSIGNED,
    OUT p_incident_id BIGINT UNSIGNED
)
BEGIN
    DECLARE v_plan_limit SMALLINT UNSIGNED DEFAULT 10;
    DECLARE v_today_count INT DEFAULT 0;

    -- Cuota diaria según plan
    SELECT COALESCE(pl.max_alerts_per_day, 10)
      INTO v_plan_limit
      FROM users u
      LEFT JOIN subscriptions s ON s.user_id = u.id AND s.status='active'
      LEFT JOIN plans pl        ON pl.id = s.plan_id
     WHERE u.id = p_user_id LIMIT 1;

    SELECT COUNT(*) INTO v_today_count
      FROM incidents
     WHERE user_id = p_user_id
       AND created_at >= CURDATE();

    IF v_today_count >= v_plan_limit THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Quota de alertas diaria excedida para el plan actual';
    END IF;

    INSERT INTO incidents
        (user_id, category_id, district_id, title, description, lat, lng, severity, status)
    VALUES
        (p_user_id, p_category_id, p_district_id, p_title, p_description, p_lat, p_lng, p_severity, 'pending');

    SET p_incident_id = LAST_INSERT_ID();

    INSERT INTO audit_log (user_id, action, entity, entity_id, meta_json)
    VALUES (p_user_id, 'create', 'incident', p_incident_id,
            JSON_OBJECT('category_id', p_category_id, 'severity', p_severity));

    -- Notificar suscriptores cuyo radio cubre el punto
    INSERT INTO notifications (user_id, incident_id, type, message)
    SELECT s.user_id, p_incident_id, 'geo_alert',
           CONCAT('Nuevo incidente cerca: ', p_title)
      FROM alert_subscriptions s
     WHERE s.active = 1
       AND (s.category_id IS NULL OR s.category_id = p_category_id)
       AND p_severity >= s.min_severity
       AND fn_haversine_km(s.center_lat, s.center_lng, p_lat, p_lng) <= s.radius_km
       AND s.user_id <> p_user_id;
END$$

-- ----------------------------------------------------------------------------
-- sp_verify_incident : moderador valida/rechaza
-- ----------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS sp_verify_incident$$
CREATE PROCEDURE sp_verify_incident(
    IN p_moderator_id INT UNSIGNED,
    IN p_incident_id  BIGINT UNSIGNED,
    IN p_new_status   VARCHAR(16)
)
BEGIN
    DECLARE v_role VARCHAR(32);
    SELECT r.name INTO v_role
      FROM users u JOIN roles r ON r.id = u.role_id
     WHERE u.id = p_moderator_id;

    IF v_role NOT IN ('moderator','admin') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Solo moderadores pueden verificar';
    END IF;

    IF p_new_status NOT IN ('verified','resolved','dismissed') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Estado invalido';
    END IF;

    UPDATE incidents
       SET status      = p_new_status,
           verified_by = p_moderator_id,
           verified_at = NOW()
     WHERE id = p_incident_id;

    INSERT INTO audit_log (user_id, action, entity, entity_id, meta_json)
    VALUES (p_moderator_id, CONCAT('verify:', p_new_status), 'incident', p_incident_id, NULL);
END$$

-- ----------------------------------------------------------------------------
-- sp_nearby_incidents : consulta cercana paginada (usada por la API)
-- ----------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS sp_nearby_incidents$$
CREATE PROCEDURE sp_nearby_incidents(
    IN p_lat       DECIMAL(10,7),
    IN p_lng       DECIMAL(10,7),
    IN p_radius_km DECIMAL(6,2),
    IN p_limit     INT
)
BEGIN
    SELECT v.*, fn_haversine_km(p_lat, p_lng, v.lat, v.lng) AS distance_km
      FROM v_incidents_full v
     WHERE fn_haversine_km(p_lat, p_lng, v.lat, v.lng) <= p_radius_km
       AND v.status IN ('pending','verified')
     ORDER BY distance_km ASC
     LIMIT p_limit;
END$$

-- ----------------------------------------------------------------------------
-- sp_upgrade_plan : activa/extiende suscripción
-- ----------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS sp_upgrade_plan$$
CREATE PROCEDURE sp_upgrade_plan(
    IN p_user_id INT UNSIGNED,
    IN p_plan_id TINYINT UNSIGNED,
    IN p_months  TINYINT UNSIGNED
)
BEGIN
    UPDATE subscriptions
       SET status='cancelled'
     WHERE user_id = p_user_id AND status='active';

    INSERT INTO subscriptions (user_id, plan_id, started_at, expires_at, status)
    VALUES (p_user_id, p_plan_id, NOW(), DATE_ADD(NOW(), INTERVAL p_months MONTH), 'active');

    INSERT INTO audit_log (user_id, action, entity, entity_id, meta_json)
    VALUES (p_user_id, 'upgrade', 'plan', p_plan_id, JSON_OBJECT('months', p_months));
END$$

-- ----------------------------------------------------------------------------
-- sp_rate_limit_check : devuelve si identifier esta bloqueado
-- ----------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS sp_rate_limit_check$$
CREATE PROCEDURE sp_rate_limit_check(
    IN  p_kind       VARCHAR(16),
    IN  p_identifier VARCHAR(190),
    IN  p_max        INT,
    IN  p_window_sec INT,
    OUT p_locked     TINYINT
)
BEGIN
    DECLARE v_failures INT DEFAULT 0;
    SELECT COUNT(*) INTO v_failures
      FROM auth_attempts
     WHERE kind = p_kind
       AND identifier = p_identifier
       AND success = 0
       AND created_at >= (NOW() - INTERVAL p_window_sec SECOND);
    SET p_locked = IF(v_failures >= p_max, 1, 0);
END$$

DELIMITER ;
