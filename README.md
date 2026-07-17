# Monitor Metrobús API

API del sistema de monitoreo en tiempo real del Metrobús de la CDMX.
Detecta el momento en que un autobús pasa por una estación y
brinda esa información a través de una API REST con datos
en formato GeoJSON.

## Funcion

- Autentica contra la API de SONDA (operador del sistema GTFS de
  Metrobús) y actualiza cada 30 segundos.
- Detecta cuándo un vehículo entra al radio de una estación y registra
  el evento.
- Expone endpoints REST para consultar la estación más cercana a un
  punto GPS, el historial (volumen limitado) de pasos por estación y ruta, y datos
  geográficos en GeoJSON para visualización en mapas.

## Stack

- **Python 3.12**, **FastAPI**, **asyncpg**
- **PostgreSQL 16** + **PostGIS 3.4** (para consultas espaciales)
- **Docker Compose**

## Arquitectura

El proyecto sigue el patrón **Controller → Service → Repository**:

```
app/
  controllers/       # Manejo de HTTP: recibe requests, devuelve responses
  services/          # Lógica de negocio: worker de polling, cliente del feed, funciones geo
  repositories/      # Acceso a datos: SQL con asyncpg.
  entities/          # Contratos de datos entre capas (usamos Pydantic)
  db/                # Conexión a BD y DDL del esquema
  core/              # Configuración (variables de entorno)
  api/routes/        # Endpoints de prueba y salud del sistema.
scripts/             # ETL de datos estáticos
```

## Base de datos

### Tablas estáticas
Cargadas una sola vez desde el GTFS estático oficial:

| Tabla | Descripción |
|-------|-------------|
| `rutas` | rutas/ramales con nombre, color y agencia |
| `estaciones` | estaciones con coordenadas y ubicacion |
| `ruta_estaciones` | Relación ruta-estación con sentido y orden |
| `shapes` | puntos de polilínea para trazar las rutas en el mapa |

### Tablas dinámicas
Alimentadas por el worker de polling:

| Tabla | Descripción |
|-------|-------------|
| `vehiculos_actuales` | Última posición de cada vehículo activo, 1 registro por vehiculo | 
| `pasos_registrados` | Eventos confirmados de paso por estación, maximo 10 registros por estacion-ruta |

## Endpoints

### Estaciones
```
GET /estaciones/cercana?lat={lat}&lon={lon}
```
La estación más cercana usando el índice GIST de PostGIS, regresa algo como:
```
http://localhost:8000/estaciones/cercana?lat=19.3947&lon=-99.1433

stop_id	"f85782"
nombre	"Álamos"
lat	19.39472362659874
lon	-99.14292840265595
```

```
GET /estaciones/{stop_id}/estado
```
Todas las rutas que pasan por una estación y el último paso registrado
de cada una. Es el endpoint principal para el que se creó el proyecto.
```
http://localhost:8000/estaciones/319cb7/estado

stop_id	"319cb7"
nombre	"Indios Verdes L1"
rutas	
0	
route_id	"19492"
nombre_corto	"1"
nombre_largo	"L01a01-1 indios verdes - dr. gálvez"
color	"#D40D0D"
ultimo_paso	
vehicle_id	"69475"
label	"1034"
detectado_en	"2026-07-14T01:44:42+00:00"
1	
route_id	"19494"
nombre_corto	"1"
nombre_largo	"L01a02-1 indios verdes - insurgentes"
color	"#D40D0D"
ultimo_paso	
vehicle_id	"69514"
label	"1123"
detectado_en	"2026-07-17T18:53:44+00:00"
2	
route_id	"19499"
nombre_corto	"1"
nombre_largo	"L01a07-1 indios verdes - el caminero"
color	"#D40D0D"
ultimo_paso	
vehicle_id	"70147"
label	"1071"
detectado_en	"2026-07-14T20:10:05+00:00"
3	
route_id	"19997"
nombre_corto	"1"
nombre_largo	"L01a05-1 indios verdes - col. del valle"
color	"#D40D0D"
ultimo_paso	null
4	
route_id	"20295"
nombre_corto	"1"
nombre_largo	"L31a31-1 indios verdes - pueblo sta cruz atoyac"
color	"#42A76B"
ultimo_paso	
vehicle_id	"69734"
label	"759"
detectado_en	"2026-07-17T18:49:56+00:00"
```

### Pasos
```
GET /estaciones/{stop_id}/ultimo-paso?route_id={route_id}
```
Último paso confirmado de una ruta en una estación.

```
GET /estaciones/{stop_id}/pasos?route_id={route_id}
```
Historial reciente de pasos (maximo 10).

### GeoJSON para implementacion con mapa
```
GET /mapa/estaciones  
```
FeatureCollection de puntos (estaciones del sistema)

```
GET /mapa/vehiculos    
```
FeatureCollection de puntos (posiciones de vehiculos en tiempo real)

```
GET /mapa/rutas      
```
FeatureCollection de LineStrings (trazos de línea para dibujar el mapa.)

### Salud del sistema
```
GET /health 
```
Estado de la app (status, app, ambiente, conexión a la db).


## Requisitos

- Docker
- Docker Compose
- Credenciales de acceso a la API de SONDA.
- Archivo GTFS estático proporcionado por el Metrobus (es un archivo `.zip`)

## Instalación

```bash
# 1. Levantar los contenedores (app + PostgreSQL/PostGIS)
docker compose up --build

# 2. Verificar que esté saludable
curl http://localhost:8000/health

# 3. Cargar los datos estáticos del GTFS
docker compose cp ./file.zip api:/code/file.zip
docker compose exec api python -m scripts.cargar_gtfs_estatico /code/file.zip
```

El worker de polling arranca automáticamente con la app y comienza a
detectar pasos de inmediato.

## Detección de pasos

Un paso se confirma cuando un vehículo transiciona de **fuera** a
**dentro** del radio de una estación (70 metros por defecto,
configurable con `STATION_RADIUS_METERS`). El timestamp registrado
corresponde al GPS del vehículo.

## Notas

La API de SONDA devuelve URLs con vigencia de 10
minutos. El cliente las cachea y
las renueva antes de que expiren, sin intervención
manual.

Los timestamps del feed están en Unix epoch (UTC).
