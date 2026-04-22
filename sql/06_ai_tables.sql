-- ============================================================================
-- 06_ai_tables.sql
-- Additional tables for AI moderation, payment methods, alert preferences,
-- and notification logging.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- AI Analysis Results
-- Stores moderation decisions from the AIService for each incident.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai_analyses (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    incident_id BIGINT NOT NULL,
    decision ENUM('approved','review','rejected') NOT NULL DEFAULT 'review',
    confidence DECIMAL(3,2) NOT NULL DEFAULT 0.50,
    reason VARCHAR(500),
    flags JSON,
    alert_level ENUM('none','low','medium','high','critical') DEFAULT 'none',
    model_used VARCHAR(64),
    tokens_used INT DEFAULT 0,
    latency_ms INT DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE,
    INDEX idx_ai_decision (decision),
    INDEX idx_ai_incident (incident_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Payment Methods
-- Stores tokenized card info per user (no raw card numbers).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payment_methods (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    card_last4 CHAR(4) NOT NULL,
    card_brand VARCHAR(20) DEFAULT 'unknown',
    card_name VARCHAR(60) NOT NULL,
    card_expiry VARCHAR(5) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- User Alert Preferences
-- Per-user notification settings (channels, quiet hours, category filters).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_alert_preferences (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    push_enabled TINYINT(1) DEFAULT 1,
    email_enabled TINYINT(1) DEFAULT 0,
    min_alert_level ENUM('low','medium','high','critical') DEFAULT 'medium',
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    categories_filter JSON,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Notification Log
-- Tracks every notification sent, for analytics and delivery confirmation.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notification_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    notification_id BIGINT,
    user_id INT NOT NULL,
    channel ENUM('app','push','email','webhook') DEFAULT 'app',
    status ENUM('sent','delivered','read','failed') DEFAULT 'sent',
    sent_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_notif_log_user (user_id, sent_at)
) ENGINE=InnoDB;
