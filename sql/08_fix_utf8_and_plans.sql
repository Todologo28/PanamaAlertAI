-- ============================================================================
-- 08_fix_utf8_and_plans.sql
-- 1. Fix charset/collation for all tables to utf8mb4
-- 2. Ensure plans table has correct limits for Free/Pro/Enterprise
-- ============================================================================

-- Fix database default charset
ALTER DATABASE panama_alert CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Fix critical tables charset
ALTER TABLE users        CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE incidents    CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE incident_comments CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE incident_categories CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE notifications CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE ai_analyses  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE plans        CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE subscriptions CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE payment_methods CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Ensure plans exist with correct differentiated limits
-- Free: 10 alerts/day, 1 geofence, no API, no priority support
-- Pro: 100 alerts/day, 5 geofences, API access, no priority support
-- Enterprise: 999 alerts/day, 50 geofences, API access, priority support

INSERT INTO plans (name, price_monthly_usd, max_alerts_per_day, max_geo_fences, api_access, priority_support, features_json)
VALUES
  ('Free', 0.00, 10, 1, FALSE, FALSE, '["Mapa en tiempo real","10 reportes por dia","1 zona de alerta","Validacion IA basica"]'),
  ('Pro', 9.99, 100, 5, TRUE, FALSE, '["Todo en Free","100 reportes por dia","5 zonas de alerta","Acceso API completo","Validacion IA avanzada","Historial 90 dias","Alertas prioritarias","Exportacion CSV/JSON"]'),
  ('Enterprise', 29.99, 999, 50, TRUE, TRUE, '["Todo en Pro","Reportes ilimitados","50 zonas de alerta","API con webhooks","IA dedicada + moderacion","Historial completo","Alertas en tiempo real","Exportacion avanzada","Soporte 24/7 dedicado"]')
ON DUPLICATE KEY UPDATE
  price_monthly_usd = VALUES(price_monthly_usd),
  max_alerts_per_day = VALUES(max_alerts_per_day),
  max_geo_fences = VALUES(max_geo_fences),
  api_access = VALUES(api_access),
  priority_support = VALUES(priority_support),
  features_json = VALUES(features_json);

SELECT 'UTF-8 and plans fixed successfully' AS result;
