# Lecciones Aprendidas

## 1. Importancia de la normalizacion

Durante el desarrollo se evidencio que separar correctamente usuarios, roles, incidentes, categorias, ubicaciones, comentarios, votos y sesiones facilita el mantenimiento del sistema. La normalizacion hasta tercera forma normal evita duplicidad y permite que la informacion sea consistente para la app, la API y Power BI.

## 2. Las vistas simplifican el analisis

Power BI puede conectarse directamente a tablas, pero resulta mas ordenado consumir vistas preparadas. Las vistas como `v_incidents_full`, `v_incidents_daily_stats` y `v_bi_overview_kpis` reducen la complejidad dentro de Power BI y hacen que el dashboard sea mas facil de construir.

## 3. ORM y SQL crudo pueden convivir

El ORM ayuda en operaciones comunes porque permite trabajar con modelos Python. Sin embargo, algunas consultas avanzadas, reportes, estadisticas o procesos de seguridad son mas claras y eficientes usando SQL crudo. La combinacion de ambos enfoques permitio cumplir los requisitos y mantener flexibilidad.

## 4. La seguridad afecta las pruebas

Durante las pruebas con JMeter aparecieron respuestas `401 Unauthorized` y errores de CSRF. Esto permitio entender que una API protegida requiere token, sesion o endpoints publicos adecuados para pruebas de carga. Para evidencias de rendimiento se decidio probar un endpoint publico estable.

## 5. Power BI requiere preparar bien la base

La conexion ODBC funciono correctamente, pero crear visuales directamente desde tablas puede ser confuso. Por eso se crearon vistas especificas para KPIs y resumenes. Esta decision hizo el dashboard mas facil de armar y entender.

## 6. Los procesos ETL necesitan limpieza y validacion

Las fuentes externas no siempre tienen informacion limpia. El bot debe limpiar HTML, eliminar ruido, identificar comercios, detectar zonas y generar mensajes comprensibles. Esto demostro que el ETL no es solo cargar datos, sino transformar informacion desordenada en registros utiles.

## 7. La ubicacion es critica en una app basada en mapa

Una alerta mal ubicada reduce el valor de la plataforma. Por eso fue necesario mejorar la resolucion de ubicaciones, incluir enlaces a Google Maps y separar la informacion de zona, direccion y fuente.

## 8. La documentacion es parte del producto

Tener la app funcionando no es suficiente para una entrega academica. Es necesario explicar arquitectura, herramientas, flujo, pruebas, evidencias y cumplimiento de requisitos. La documentacion permite demostrar el trabajo de forma ordenada.

## 9. Las pruebas de rendimiento ayudan a descubrir limites

JMeter permitio simular usuarios concurrentes y observar tiempos de respuesta, errores y throughput. Esto sirve para medir estabilidad del backend y justificar mejoras futuras de infraestructura.

## 10. El despliegue en produccion requiere varias capas

La app no depende solo de Flask. Para produccion se integraron Gunicorn, systemd, Nginx, firewall, variables de entorno y MariaDB. Esto mostro que una aplicacion real necesita backend, servicio, proxy, seguridad y monitoreo basico.

## 11. Mejoras futuras identificadas

- Generar reportes PDF automaticos.
- Automatizar envio de resumenes por correo.
- Mejorar aun mas el dashboard Power BI.
- Agregar pruebas automatizadas unitarias.
- Implementar HTTPS definitivo con dominio o tunel.
- Crear monitoreo de logs y alertas de sistema.
- Optimizar consultas para alto volumen de incidentes.

## 12. Conclusion

El desarrollo de PanamaAlert permitio integrar base de datos, backend, frontend, ETL, Power BI y pruebas. La principal leccion fue que un sistema completo no se limita al codigo; tambien requiere datos bien modelados, seguridad, despliegue, visualizacion, pruebas y documentacion clara.
