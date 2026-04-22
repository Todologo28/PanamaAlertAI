# Glosario de Terminos

## API REST

Interfaz que permite que sistemas externos o el frontend se comuniquen con el backend usando HTTP. Utiliza metodos como GET, POST, PUT y DELETE.

## Backend

Parte del sistema que procesa la logica de negocio, se conecta a la base de datos y expone endpoints para la aplicacion.

## Base de datos relacional

Tipo de base de datos que organiza informacion en tablas relacionadas mediante llaves primarias y foraneas.

## BI

Business Intelligence. Conjunto de herramientas y procesos para analizar datos y convertirlos en informacion visual para la toma de decisiones.

## CRUD

Create, Read, Update, Delete. Operaciones basicas para crear, consultar, actualizar y eliminar registros.

## CSRF

Cross-Site Request Forgery. Ataque donde un sitio intenta ejecutar acciones no autorizadas usando una sesion activa. Se mitiga usando tokens CSRF.

## Dashboard

Tablero visual que muestra indicadores, graficas, mapas y resumenes para analizar informacion.

## DSN

Data Source Name. Configuracion ODBC que guarda los datos de conexion hacia una base de datos.

## Endpoint

Ruta especifica de una API. Ejemplo: `/api/incidents`.

## ETL

Extract, Transform, Load. Proceso para extraer datos, transformarlos y cargarlos en una base de datos.

## Flask

Framework de Python utilizado para construir aplicaciones web y APIs.

## Foreign Key

Llave foranea. Campo que relaciona una tabla con otra.

## Frontend

Parte visual de la aplicacion con la que interactua el usuario. Incluye HTML, CSS y JavaScript.

## Geo-fence

Zona geografica definida para activar alertas cuando ocurre un incidente dentro de un radio o area.

## Geocodificacion

Proceso de convertir una direccion, comercio o lugar en coordenadas de latitud y longitud.

## Gunicorn

Servidor WSGI usado para ejecutar aplicaciones Flask en produccion.

## Haversine

Formula matematica usada para calcular distancia entre dos puntos geograficos usando latitud y longitud.

## HTTP

Protocolo utilizado para comunicacion web entre clientes y servidores.

## Incidente

Registro principal de PanamaAlert. Representa una alerta, reporte ciudadano, oferta, emergencia o evento geolocalizado.

## JMeter

Herramienta usada para pruebas de carga y rendimiento. Simula muchos usuarios haciendo peticiones al sistema.

## JSON

Formato ligero de intercambio de datos usado en APIs.

## JWT

JSON Web Token. Token firmado usado para autenticacion y autorizacion en APIs.

## MariaDB

Sistema gestor de base de datos relacional usado en el proyecto.

## Nginx

Servidor web usado como reverse proxy para recibir trafico y enviarlo hacia Gunicorn.

## ODBC

Open Database Connectivity. Tecnologia que permite conectar herramientas como Power BI con bases de datos como MariaDB.

## ORM

Object Relational Mapper. Herramienta que permite trabajar con tablas de base de datos como clases u objetos en codigo.

## Power BI

Herramienta de Microsoft usada para crear dashboards interactivos conectados a fuentes de datos.

## Procedimiento almacenado

Bloque de SQL guardado dentro de la base de datos para ejecutar una tarea especifica.

## Rate limiting

Tecnica para limitar la cantidad de peticiones o acciones que puede realizar un usuario en un periodo de tiempo.

## Reverse proxy

Servidor intermedio que recibe solicitudes del cliente y las redirige a la aplicacion interna.

## SQL

Structured Query Language. Lenguaje usado para consultar y modificar bases de datos relacionales.

## SQL crudo

Consulta SQL escrita directamente, sin usar ORM.

## SQLAlchemy

ORM de Python usado para conectar Flask con MariaDB.

## systemd

Sistema de administracion de servicios en Linux. Permite iniciar, detener y monitorear PanamaAlert como servicio.

## Tercera Forma Normal

Regla de normalizacion que busca eliminar dependencias transitivas y reducir redundancia en el modelo relacional.

## Throughput

Cantidad de peticiones que un sistema puede procesar en un periodo de tiempo. Se mide en pruebas de rendimiento.

## Token

Cadena usada para autenticar o autorizar solicitudes.

## Vista SQL

Consulta guardada en la base de datos que se comporta como una tabla virtual.
