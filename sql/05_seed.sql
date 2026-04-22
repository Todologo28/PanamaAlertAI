-- ============================================================================
-- Datos semilla
-- Password default para usuarios seed: "Password123"
-- Hash generado con werkzeug generate_password_hash (scrypt).
-- Al arrancar la app el primer admin puede cambiar su password.
-- ============================================================================
USE panama_alert;

INSERT INTO roles (name, description) VALUES
    ('user',      'Usuario ciudadano'),
    ('moderator', 'Verifica incidentes'),
    ('admin',     'Administrador del sistema');

INSERT INTO plans (name, price_monthly_usd, max_alerts_per_day, max_geo_fences, api_access, priority_support, features_json) VALUES
    ('Free',       0.00,  5,  1, 0, 0, JSON_OBJECT('ads', true,  'history_days', 7)),
    ('Pro',        4.99, 50,  5, 1, 0, JSON_OBJECT('ads', false, 'history_days', 90,  'push', true)),
    ('Enterprise',49.00, 1000,50,1, 1, JSON_OBJECT('ads', false, 'history_days', 365, 'push', true, 'sla', '99.9'));

INSERT INTO provinces (code, name) VALUES
    ('PA',  'Panamá'),
    ('CO',  'Colón'),
    ('CH',  'Chiriquí'),
    ('HE',  'Herrera'),
    ('LS',  'Los Santos'),
    ('VE',  'Veraguas'),
    ('CC',  'Coclé'),
    ('BT',  'Bocas del Toro'),
    ('DA',  'Darién'),
    ('PO',  'Panamá Oeste');

INSERT INTO districts (province_id, name) VALUES
    ((SELECT id FROM provinces WHERE code='PA'), 'Panamá'),
    ((SELECT id FROM provinces WHERE code='PA'), 'San Miguelito'),
    ((SELECT id FROM provinces WHERE code='PA'), 'Chepo'),
    ((SELECT id FROM provinces WHERE code='PO'), 'La Chorrera'),
    ((SELECT id FROM provinces WHERE code='PO'), 'Arraiján'),
    ((SELECT id FROM provinces WHERE code='CO'), 'Colón'),
    ((SELECT id FROM provinces WHERE code='CH'), 'David'),
    ((SELECT id FROM provinces WHERE code='HE'), 'Chitré'),
    ((SELECT id FROM provinces WHERE code='VE'), 'Santiago'),
    ((SELECT id FROM provinces WHERE code='CC'), 'Penonomé');

INSERT INTO incident_categories (name, icon, color_hex, default_severity) VALUES
    ('Robo',           'mask',      '#e74c3c', 4),
    ('Accidente',      'car-crash', '#f39c12', 3),
    ('Incendio',       'fire',      '#c0392b', 5),
    ('Inundación',     'water',     '#3498db', 4),
    ('Sospechoso',     'eye',       '#9b59b6', 2),
    ('Vandalismo',     'spray',     '#7f8c8d', 2),
    ('Emergencia médica','plus',    '#e67e22', 5),
    ('Corte de luz',   'bolt',      '#f1c40f', 2);

-- Usuario admin demo (password = Password123)
-- (hash scrypt werkzeug; reemplazar en producción)
INSERT INTO users (username, email, password_hash, full_name, role_id, email_verified)
VALUES
    ('admin',     'admin@panamaalert.pa',
     'scrypt:32768:8:1$xEFSEED$PLACEHOLDER_REEMPLAZAR_EN_PROD',
     'Administrador', (SELECT id FROM roles WHERE name='admin'), 1),
    ('moderator', 'mod@panamaalert.pa',
     'scrypt:32768:8:1$xEFSEED$PLACEHOLDER_REEMPLAZAR_EN_PROD',
     'Moderador Demo', (SELECT id FROM roles WHERE name='moderator'), 1);

INSERT INTO subscriptions (user_id, plan_id, status, expires_at)
SELECT u.id, (SELECT id FROM plans WHERE name='Enterprise'), 'active', DATE_ADD(NOW(), INTERVAL 12 MONTH)
FROM users u WHERE u.username='admin';
