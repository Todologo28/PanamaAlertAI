-- ============================================================================
-- PanamaAlert Pro - Schema relacional (3FN)
-- MariaDB 10.5+ / InnoDB / utf8mb4
-- ============================================================================
DROP DATABASE IF EXISTS panama_alert;
CREATE DATABASE panama_alert CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE panama_alert;

SET FOREIGN_KEY_CHECKS=0;

-- ---------- Catálogos geográficos (normalizados) ---------------------------
CREATE TABLE provinces (
    id           SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    code         VARCHAR(8)   NOT NULL UNIQUE,
    name         VARCHAR(80)  NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE districts (
    id           SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    province_id  SMALLINT UNSIGNED NOT NULL,
    name         VARCHAR(120) NOT NULL,
    UNIQUE KEY uk_district (province_id, name),
    CONSTRAINT fk_district_province FOREIGN KEY (province_id)
        REFERENCES provinces(id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ---------- Roles, planes, usuarios ----------------------------------------
CREATE TABLE roles (
    id           TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(32)  NOT NULL UNIQUE,
    description  VARCHAR(255) NULL
) ENGINE=InnoDB;

CREATE TABLE plans (
    id                  TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name                VARCHAR(32)   NOT NULL UNIQUE,
    price_monthly_usd   DECIMAL(8,2)  NOT NULL DEFAULT 0.00,
    max_alerts_per_day  SMALLINT UNSIGNED NOT NULL DEFAULT 10,
    max_geo_fences      SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    api_access          TINYINT(1)    NOT NULL DEFAULT 0,
    priority_support    TINYINT(1)    NOT NULL DEFAULT 0,
    features_json       JSON          NULL
) ENGINE=InnoDB;

CREATE TABLE users (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(32)  NOT NULL UNIQUE,
    email           VARCHAR(190) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    totp_secret_enc VARCHAR(255) NULL,
    totp_enabled    TINYINT(1)   NOT NULL DEFAULT 0,
    full_name       VARCHAR(120) NOT NULL,
    cedula          VARCHAR(32)  NULL,
    phone           VARCHAR(32)  NULL,
    district_id     SMALLINT UNSIGNED NULL,
    role_id         TINYINT UNSIGNED NOT NULL,
    is_active       TINYINT(1)   NOT NULL DEFAULT 1,
    email_verified  TINYINT(1)   NOT NULL DEFAULT 0,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at   DATETIME     NULL,
    CONSTRAINT fk_user_role FOREIGN KEY (role_id) REFERENCES roles(id),
    CONSTRAINT fk_user_district FOREIGN KEY (district_id) REFERENCES districts(id),
    INDEX idx_user_district (district_id),
    INDEX idx_user_role (role_id)
) ENGINE=InnoDB;

CREATE TABLE subscriptions (
    id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id      INT UNSIGNED NOT NULL,
    plan_id      TINYINT UNSIGNED NOT NULL,
    started_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at   DATETIME NULL,
    status       ENUM('active','cancelled','expired','trial') NOT NULL DEFAULT 'active',
    CONSTRAINT fk_sub_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_sub_plan FOREIGN KEY (plan_id) REFERENCES plans(id),
    INDEX idx_sub_user_status (user_id, status),
    INDEX idx_sub_expires (expires_at)
) ENGINE=InnoDB;

-- ---------- Incidentes ------------------------------------------------------
CREATE TABLE incident_categories (
    id               TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name             VARCHAR(64) NOT NULL UNIQUE,
    icon             VARCHAR(32) NULL,
    color_hex        CHAR(7)     NULL,
    default_severity TINYINT UNSIGNED NOT NULL DEFAULT 3
) ENGINE=InnoDB;

CREATE TABLE incidents (
    id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id      INT UNSIGNED NOT NULL,
    category_id  TINYINT UNSIGNED NOT NULL,
    district_id  SMALLINT UNSIGNED NULL,
    title        VARCHAR(160) NOT NULL,
    description  VARCHAR(1000) NOT NULL,
    lat          DECIMAL(10,7) NOT NULL,
    lng          DECIMAL(10,7) NOT NULL,
    severity     TINYINT UNSIGNED NOT NULL DEFAULT 3,   -- 1..5
    status       ENUM('pending','verified','resolved','dismissed') NOT NULL DEFAULT 'pending',
    verified_by  INT UNSIGNED NULL,
    verified_at  DATETIME NULL,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    expires_at   DATETIME NULL,
    CONSTRAINT fk_inc_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_inc_cat  FOREIGN KEY (category_id) REFERENCES incident_categories(id),
    CONSTRAINT fk_inc_dist FOREIGN KEY (district_id) REFERENCES districts(id),
    CONSTRAINT fk_inc_ver  FOREIGN KEY (verified_by) REFERENCES users(id),
    CONSTRAINT chk_severity CHECK (severity BETWEEN 1 AND 5),
    INDEX idx_inc_user (user_id),
    INDEX idx_inc_cat  (category_id),
    INDEX idx_inc_status_created (status, created_at),
    INDEX idx_inc_district (district_id),
    INDEX idx_inc_geo (lat, lng)
) ENGINE=InnoDB;

CREATE TABLE incident_media (
    id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    incident_id  BIGINT UNSIGNED NOT NULL,
    media_type   ENUM('image','video','audio') NOT NULL,
    url          VARCHAR(500) NOT NULL,
    uploaded_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_media_inc FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE incident_votes (
    incident_id  BIGINT UNSIGNED NOT NULL,
    user_id      INT UNSIGNED NOT NULL,
    vote         TINYINT NOT NULL,      -- +1 / -1
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (incident_id, user_id),
    CONSTRAINT fk_vote_inc  FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE,
    CONSTRAINT fk_vote_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT chk_vote CHECK (vote IN (-1, 1))
) ENGINE=InnoDB;

CREATE TABLE incident_comments (
    id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    incident_id  BIGINT UNSIGNED NOT NULL,
    user_id      INT UNSIGNED NOT NULL,
    body         VARCHAR(1000) NOT NULL,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_com_inc  FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE,
    CONSTRAINT fk_com_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_com_inc (incident_id, created_at)
) ENGINE=InnoDB;

-- ---------- Suscripciones a alertas geo-cercadas (feature premium) ---------
CREATE TABLE alert_subscriptions (
    id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id      INT UNSIGNED NOT NULL,
    category_id  TINYINT UNSIGNED NULL,
    center_lat   DECIMAL(10,7) NOT NULL,
    center_lng   DECIMAL(10,7) NOT NULL,
    radius_km    DECIMAL(6,2)  NOT NULL DEFAULT 5.0,
    min_severity TINYINT UNSIGNED NOT NULL DEFAULT 1,
    active       TINYINT(1)    NOT NULL DEFAULT 1,
    created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_alsub_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_alsub_cat  FOREIGN KEY (category_id) REFERENCES incident_categories(id),
    INDEX idx_alsub_user (user_id, active)
) ENGINE=InnoDB;

CREATE TABLE notifications (
    id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id      INT UNSIGNED NOT NULL,
    incident_id  BIGINT UNSIGNED NULL,
    type         VARCHAR(32) NOT NULL,
    message      VARCHAR(500) NOT NULL,
    is_read      TINYINT(1)  NOT NULL DEFAULT 0,
    created_at   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_notif_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_notif_inc  FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE SET NULL,
    INDEX idx_notif_user_unread (user_id, is_read, created_at)
) ENGINE=InnoDB;

-- ---------- Seguridad / auditoría ------------------------------------------
CREATE TABLE auth_attempts (
    id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    kind         ENUM('login','token','reset','session_open') NOT NULL,
    identifier   VARCHAR(190) NOT NULL,
    ip           VARCHAR(64)  NOT NULL,
    success      TINYINT(1)   NOT NULL DEFAULT 0,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_attempts_lookup (kind, identifier, created_at)
) ENGINE=InnoDB;

CREATE TABLE active_sessions (
    id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    session_id   VARCHAR(96) NOT NULL UNIQUE,
    user_id      INT UNSIGNED NOT NULL,
    ip           VARCHAR(64)  NULL,
    user_agent   VARCHAR(512) NULL,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at   DATETIME     NOT NULL,
    CONSTRAINT fk_active_session_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_active_session_user (user_id),
    INDEX idx_active_session_expires (expires_at),
    INDEX idx_active_session_last_seen (last_seen_at)
) ENGINE=InnoDB;

CREATE TABLE audit_log (
    id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id      INT UNSIGNED NULL,
    action       VARCHAR(64)  NOT NULL,
    entity       VARCHAR(64)  NOT NULL,
    entity_id    VARCHAR(64)  NULL,
    ip           VARCHAR(64)  NULL,
    user_agent   VARCHAR(512) NULL,
    meta_json    JSON         NULL,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_audit_user (user_id, created_at),
    INDEX idx_audit_entity (entity, entity_id)
) ENGINE=InnoDB;

CREATE TABLE api_keys (
    id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id      INT UNSIGNED NOT NULL,
    name         VARCHAR(64)  NOT NULL,
    key_hash     CHAR(64)     NOT NULL UNIQUE,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_used_at DATETIME     NULL,
    revoked_at   DATETIME     NULL,
    CONSTRAINT fk_apikey_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------- ETL -------------------------------------------------------------
CREATE TABLE etl_runs (
    id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    source         VARCHAR(64) NOT NULL,
    started_at     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at    DATETIME    NULL,
    rows_read      INT UNSIGNED NOT NULL DEFAULT 0,
    rows_loaded    INT UNSIGNED NOT NULL DEFAULT 0,
    rows_failed    INT UNSIGNED NOT NULL DEFAULT 0,
    status         ENUM('running','success','failed') NOT NULL DEFAULT 'running',
    message        VARCHAR(500) NULL
) ENGINE=InnoDB;

CREATE TABLE etl_staging_incidents (
    id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    run_id       INT UNSIGNED NOT NULL,
    source       VARCHAR(64)  NOT NULL,
    external_id  VARCHAR(128) NULL,
    raw_json     JSON         NOT NULL,
    processed    TINYINT(1)   NOT NULL DEFAULT 0,
    error        VARCHAR(500) NULL,
    loaded_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_stg_run FOREIGN KEY (run_id) REFERENCES etl_runs(id) ON DELETE CASCADE,
    INDEX idx_stg_processed (processed)
) ENGINE=InnoDB;

SET FOREIGN_KEY_CHECKS=1;
