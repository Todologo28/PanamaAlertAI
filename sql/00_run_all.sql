-- Ejecuta todos los scripts en orden desde la raíz sql/
-- Uso en tu VM OL8:
--   mysql -u root -p < 00_run_all.sql
SOURCE 01_schema.sql;
SOURCE 02_views.sql;
SOURCE 03_procedures.sql;
SOURCE 04_triggers.sql;
SOURCE 05_seed.sql;
SELECT 'PanamaAlert DB instalada' AS status;
