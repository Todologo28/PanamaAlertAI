# Lecciones Aprendidas

## 1. La base de datos no debe ser un detalle

Mover reglas importantes a MariaDB da mas consistencia que dejarlas solo en el backend. Procedimientos, vistas y restricciones ayudan a que la logica no dependa de una sola interfaz.

## 2. ORM y SQL crudo pueden convivir bien

El ORM agiliza el CRUD diario, pero las consultas crudas y procedimientos siguen siendo utiles para enriquecimiento, BI y operaciones avanzadas.

## 3. ETL con staging da mas control

Tener una etapa intermedia permite reprocesar datos y auditar mejor los errores sin contaminar las tablas finales.

## 4. Seguridad real no es solo login

CSRF, cabeceras, endurecimiento de sesiones, validacion de uploads y limitacion por IP elevan mucho la robustez de una app expuesta.

## 5. Mapa y UX afectan la percepcion de calidad

Un mapa con clustering, paneles explicativos y GPS mejora no solo lo visual, sino tambien la utilidad del sistema.

## 6. Moderacion y trazabilidad importan

No basta con recibir reportes; hay que poder explicarlos, corregirlos, descartar duplicados y justificar decisiones.

## 7. La documentacion pesa tanto como el codigo

Para un proyecto academico, una matriz de cumplimiento y un manual claro hacen mas facil defender que el proyecto realmente cubre el PDF.
