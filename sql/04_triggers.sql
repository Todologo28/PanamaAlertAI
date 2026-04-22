-- ============================================================================
-- Triggers de auditoría e integridad
-- ============================================================================
USE panama_alert;

DELIMITER $$

-- Auditar cualquier UPDATE en incidents
DROP TRIGGER IF EXISTS trg_incidents_after_update$$
CREATE TRIGGER trg_incidents_after_update
AFTER UPDATE ON incidents
FOR EACH ROW
BEGIN
    IF OLD.status <> NEW.status OR OLD.severity <> NEW.severity THEN
        INSERT INTO audit_log (user_id, action, entity, entity_id, meta_json)
        VALUES (NEW.verified_by, 'update', 'incident', NEW.id,
                JSON_OBJECT('old_status', OLD.status, 'new_status', NEW.status,
                            'old_severity', OLD.severity, 'new_severity', NEW.severity));
    END IF;
END$$

-- Auditar DELETE de incidents
DROP TRIGGER IF EXISTS trg_incidents_after_delete$$
CREATE TRIGGER trg_incidents_after_delete
AFTER DELETE ON incidents
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (user_id, action, entity, entity_id, meta_json)
    VALUES (OLD.user_id, 'delete', 'incident', OLD.id,
            JSON_OBJECT('title', OLD.title, 'status', OLD.status));
END$$

-- Expirar incidentes resueltos tras 30 días automáticamente al actualizarse
DROP TRIGGER IF EXISTS trg_incidents_before_update$$
CREATE TRIGGER trg_incidents_before_update
BEFORE UPDATE ON incidents
FOR EACH ROW
BEGIN
    IF NEW.status = 'resolved' AND NEW.expires_at IS NULL THEN
        SET NEW.expires_at = DATE_ADD(NOW(), INTERVAL 30 DAY);
    END IF;
END$$

DELIMITER ;
