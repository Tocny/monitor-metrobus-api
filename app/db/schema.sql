-- ============================================================
-- Esquema de la base de datos -- Monitor Metrobus (PostgreSQL + PostGIS)
-- ============================================================
--
--   docker compose exec db pg_dump -U metrobus -d metrobus --schema-only
-- ============================================================

CREATE EXTENSION IF NOT EXISTS postgis;

-- ----------------------------------------------------------------
-- DATOS ESTATICOS (cargados una sola vez via
-- scripts/cargar_gtfs_estatico.py, no crecen con el tiempo)
-- ----------------------------------------------------------------

-- ----------------------------------------------------------------
-- Tabla: rutas
-- ----------------------------------------------------------------
-- Una linea/ramal/sentido de Metrobus. route_id es el MISMO id que usa el feed en tiempo real 

CREATE TABLE IF NOT EXISTS rutas (
    route_id      TEXT NOT NULL PRIMARY KEY,
    nombre_corto  TEXT,  
    nombre_largo  TEXT,  
    color         TEXT,
    agencia       TEXT
);

COMMENT ON TABLE rutas IS 'Catálogo de rutas del Metrobús. Cada registro representa un ramal/sentido específico (route_id único del GTFS). Se carga una sola vez desde el GTFS estático y no cambia con el tiempo.';

COMMENT ON COLUMN rutas.route_id IS 'Identificador único de la ruta según el GTFS estático. Es el mismo ID que usa el feed en tiempo real (vehicle.trip.route_id).';
COMMENT ON COLUMN rutas.nombre_corto IS 'Número corto de la línea (ej. "1", "3", "7"). Es lo que el usuario reconoce como "línea del Metrobús".';
COMMENT ON COLUMN rutas.nombre_largo IS 'Descripción detallada del ramal y sentido (ej. "L01a21-2 col. del valle - tepalcates"). Proviene de route_long_name del GTFS.';
COMMENT ON COLUMN rutas.color IS 'Color asociado a la línea (código hexadecimal o nombre). Usado para la interfaz de usuario.';
COMMENT ON COLUMN rutas.agencia IS 'Identificador de la agencia (normalmente "1339" para Metrobús).';

-- ----------------------------------------------------------------
-- Tabla: estaciones
-- ----------------------------------------------------------------
-- Una estacion fisica (stop_id del GTFS), con su ubicacion geografica.

CREATE TABLE IF NOT EXISTS estaciones (
    stop_id    TEXT NOT NULL PRIMARY KEY,
    nombre     TEXT NOT NULL,
    ubicacion  GEOGRAPHY(POINT, 4326) NOT NULL,
    lat        DOUBLE PRECISION NOT NULL,
    lon        DOUBLE PRECISION NOT NULL
);

COMMENT ON TABLE estaciones IS 'Catálogo de estaciones físicas del Metrobús. Cada estación tiene una ubicación geográfica precisa (punto) y un stop_id estable del GTFS. Se carga una vez desde el GTFS estático.';

COMMENT ON COLUMN estaciones.stop_id IS 'Identificador único de la estación según el GTFS (ej. "fa077f"). Es la llave para enlazar con el feed en tiempo real.';
COMMENT ON COLUMN estaciones.nombre IS 'Nombre público de la estación (ej. "Potrero", "Insurgentes").';
COMMENT ON COLUMN estaciones.ubicacion IS 'Ubicación geográfica como punto en SRID 4326 (WGS84). Usa el tipo GEOGRAPHY para cálculos de distancia precisos en metros.';
COMMENT ON COLUMN estaciones.lat IS 'Latitud en grados decimales (columna redundante para facilitar consultas simples).';
COMMENT ON COLUMN estaciones.lon IS 'Longitud en grados decimales (columna redundante para facilitar consultas simples).';


-- ----------------------------------------------------------------
-- Índice: ix_estaciones_ubicacion
-- ----------------------------------------------------------------
-- Indice espacial GIST -- permite "estacion mas cercana" como consulta
-- nativa indexada (ORDER BY ubicacion <-> punto LIMIT 1).

CREATE INDEX IF NOT EXISTS ix_estaciones_ubicacion ON estaciones USING GIST (ubicacion);

COMMENT ON INDEX ix_estaciones_ubicacion IS 'Índice espacial GIST sobre ubicacion. Permite consultas eficientes de "estación más cercana" usando el operador <-> (KNN) y ST_Distance.';

-- ----------------------------------------------------------------
-- Tabla: ruta_estaciones
-- ----------------------------------------------------------------
-- Que estaciones pertenecen a que ruta, en que orden y sentido.
-- Derivado de trips.txt + stop_times.txt durante el ETL.

CREATE TABLE IF NOT EXISTS ruta_estaciones (
    route_id  TEXT NOT NULL REFERENCES rutas(route_id),
    stop_id   TEXT NOT NULL REFERENCES estaciones(stop_id),
    sentido   TEXT NOT NULL,
    orden     INTEGER NOT NULL, 
    PRIMARY KEY (route_id, stop_id, sentido)
);

COMMENT ON TABLE ruta_estaciones IS 'Relación que asigna estaciones a rutas, definiendo el orden en que aparecen en cada sentido (IDA/REGRESO). Se deriva de trips.txt y stop_times.txt del GTFS durante el ETL.';

COMMENT ON COLUMN ruta_estaciones.route_id IS 'Referencia a la ruta (rutas.route_id).';
COMMENT ON COLUMN ruta_estaciones.stop_id IS 'Referencia a la estación (estaciones.stop_id).';
COMMENT ON COLUMN ruta_estaciones.sentido IS 'Dirección de la ruta: "IDA" o "REGRESO". Determina si la estación pertenece al viaje de ida o de vuelta.';
COMMENT ON COLUMN ruta_estaciones.orden IS 'Posición de la estación en la ruta (1 = primera estación). Usado para mantener el orden secuencial de las paradas.';


-- ----------------------------------------------------------------
-- DATOS DINAMICOS (alimentados por el feed GTFS-RT, Fase 3)
-- Politicas de retencion DISTINTAS -- ver comentarios en cada tabla
-- ----------------------------------------------------------------


-- ----------------------------------------------------------------
-- Tabla: vehiculos_actuales
-- ----------------------------------------------------------------
-- Ultima posicion conocida de cada vehiculo. Una fila por vehiculo,
-- se sobreescribe (UPSERT) cada ciclo de 30s. NUNCA crece -- siempre
-- tiene como maximo tantas filas como camiones activos (~800-900).

CREATE TABLE IF NOT EXISTS vehiculos_actuales (
    vehicle_id          TEXT NOT NULL PRIMARY KEY,  
    label                TEXT,                       
    route_id             TEXT,
    lat                  DOUBLE PRECISION NOT NULL,
    lon                  DOUBLE PRECISION NOT NULL,
    velocidad            DOUBLE PRECISION,
    feed_timestamp        INTEGER NOT NULL,              
    estacion_actual_id   TEXT,                       
    actualizado_en       TIMESTAMPTZ
);

COMMENT ON TABLE vehiculos_actuales IS 'Estado actual de cada vehículo. Se actualiza cada 30 segundos con el feed GTFS-RT. Esta tabla siempre tiene ~800-900 filas (una por vehículo activo). No crece con el tiempo.';

COMMENT ON COLUMN vehiculos_actuales.vehicle_id IS 'Identificador estable del vehículo (vehicle.vehicle.id del feed). NO es entity.id (que cambia entre lecturas). Es la llave principal.';
COMMENT ON COLUMN vehiculos_actuales.label IS 'Número visible del camión (ej. "1203"). Proviene de vehicle.vehicle.label. Útil para identificación por parte del usuario.';
COMMENT ON COLUMN vehiculos_actuales.route_id IS 'ID de la ruta que está cubriendo actualmente (vehicle.trip.route_id). Enlaza con rutas.route_id.';
COMMENT ON COLUMN vehiculos_actuales.lat IS 'Última latitud reportada por el feed (grados decimales).';
COMMENT ON COLUMN vehiculos_actuales.lon IS 'Última longitud reportada por el feed (grados decimales).';
COMMENT ON COLUMN vehiculos_actuales.velocidad IS 'Velocidad del vehículo en m/s (si el feed la proporciona). Puede ser NULL.';
COMMENT ON COLUMN vehiculos_actuales.feed_timestamp IS 'Timestamp UNIX (segundos desde 1970) que el feed reporta para esta posición. Es el momento en que se tomó la medición.';
COMMENT ON COLUMN vehiculos_actuales.estacion_actual_id IS 'ID de la estación más cercana según la última lectura. Se calcula al procesar el feed (no viene directamente). Puede ser NULL si el vehículo está entre estaciones.';
COMMENT ON COLUMN vehiculos_actuales.actualizado_en IS 'Momento en que se actualizó este registro en la base de datos (TIMESTAMPTZ). Útil para saber la frescura de los datos.';


-- ----------------------------------------------------------------
-- Tabla: pasos_registrados
-- ----------------------------------------------------------------
-- El log real de pasos confirmados: "el vehiculo X paso por la
-- estacion Y a las HH:MM:SS". Se acota a los ultimos N (10 por
-- defecto, ver app/services/retencion.py) registros POR CADA
-- combinacion (estacion_id, route_id) -- no de forma global -- para
-- que una estacion muy transitada no desplace el historial de las
-- demas.

CREATE TABLE IF NOT EXISTS pasos_registrados (
    id            SERIAL PRIMARY KEY,
    estacion_id   TEXT NOT NULL REFERENCES estaciones(stop_id),
    route_id      TEXT NOT NULL REFERENCES rutas(route_id),
    vehicle_id    TEXT NOT NULL,
    label         TEXT,
    detectado_en  TIMESTAMPTZ NOT NULL
);

COMMENT ON TABLE pasos_registrados IS 'Registro histórico de pasos confirmados: cada fila indica que un vehículo pasó por una estación en un momento dado. Solo se retienen los últimos N registros por combinación (estacion_id, route_id) para evitar crecimiento infinito.';

COMMENT ON COLUMN pasos_registrados.id IS 'Identificador único autoincremental de la fila.';
COMMENT ON COLUMN pasos_registrados.estacion_id IS 'Estación donde se detectó el paso (referencia a estaciones.stop_id).';
COMMENT ON COLUMN pasos_registrados.route_id IS 'Ruta que cubría el vehículo al momento del paso (referencia a rutas.route_id).';
COMMENT ON COLUMN pasos_registrados.vehicle_id IS 'Identificador del vehículo (vehiculos_actuales.vehicle_id) que realizó el paso.';
COMMENT ON COLUMN pasos_registrados.label IS 'Número visible del camión en el momento del paso (copia para referencia histórica).';
COMMENT ON COLUMN pasos_registrados.detectado_en IS 'Momento exacto en que se detectó el paso (TIMESTAMPTZ). Usado para ordenar el historial y para la política de retención.';


-- ----------------------------------------------------------------
-- Índices de pasos_registrados
-- ----------------------------------------------------------------

CREATE INDEX IF NOT EXISTS ix_pasos_registrados_estacion_id  ON pasos_registrados (estacion_id);
COMMENT ON INDEX ix_pasos_registrados_estacion_id IS 'Índice para consultas por estación (ej. "últimos pasos en esta estación").';

CREATE INDEX IF NOT EXISTS ix_pasos_registrados_route_id     ON pasos_registrados (route_id);
COMMENT ON INDEX ix_pasos_registrados_route_id IS 'Índice para consultas por ruta (ej. "pasos de la ruta 1 en el último minuto").';

CREATE INDEX IF NOT EXISTS ix_pasos_registrados_detectado_en ON pasos_registrados (detectado_en);
COMMENT ON INDEX ix_pasos_registrados_detectado_en IS 'Índice por tiempo para consultas temporales y para la poda de registros antiguos.';

-- ----------------------------------------------------------------
-- Tabla: shapes
-- ----------------------------------------------------------------
-- Trazos geometricos de cada ruta (shape_id = route_id en este GTFS).
-- Cada fila es un punto de la polilínea, ordenado por secuencia.
-- Se usará para trazar las rutas 
CREATE TABLE IF NOT EXISTS shapes (
    route_id     TEXT NOT NULL REFERENCES rutas(route_id),
    secuencia    INTEGER NOT NULL,
    lat          DOUBLE PRECISION NOT NULL,
    lon          DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (route_id, secuencia)
);

COMMENT ON TABLE shapes IS 'Almacena los puntos (lat, lon) que forman el trazo geográfico de cada ruta. Cada fila es un punto de la polilínea, ordenado por secuencia. route_id es la clave foránea a rutas.';

COMMENT ON COLUMN shapes.route_id IS 'Identificador de la ruta. Coincide con rutas.route_id y con vehicle.trip.route_id del feed GTFS-RT.';
COMMENT ON COLUMN shapes.secuencia IS 'Orden del punto en la polilínea. Los puntos se deben unir en este orden para dibujar la ruta correctamente.';
COMMENT ON COLUMN shapes.lat IS 'Latitud del punto en el sistema de coordenadas WGS84 (EPSG:4326).';
COMMENT ON COLUMN shapes.lon IS 'Longitud del punto en el sistema de coordenadas WGS84 (EPSG:4326).';

-- ----------------------------------------------------------------
-- La base de datos.
-- ----------------------------------------------------------------
COMMENT ON DATABASE metrobus IS 'Base de datos del proyecto Monitor Metrobús. Contiene datos estáticos (rutas, estaciones) y dinámicos (vehículos en tiempo real, pasos registrados). Usa PostGIS para cálculos geográficos.';

-- ----------------------------------------------------------------
-- Consulta de ejemplo: estacion mas cercana a un punto (lat, lon),
-- aprovechando el indice GIST -- la usaremos en la Fase 4
-- ----------------------------------------------------------------
-- SELECT stop_id, nombre,
--        ST_Distance(ubicacion, ST_SetSRID(ST_MakePoint($lon, $lat), 4326)::geography) AS distancia_metros
-- FROM estaciones
-- ORDER BY ubicacion <-> ST_SetSRID(ST_MakePoint($lon, $lat), 4326)::geography
-- LIMIT 1;

-- ----------------------------------------------------------------
-- Consulta de ejemplo: poda de pasos_registrados a los ultimos N
-- por estacion+ruta (la corre el worker despues de cada insercion,
-- ver app/services/retencion.py -- aqui solo de referencia)
-- ----------------------------------------------------------------
-- DELETE FROM pasos_registrados
-- WHERE id IN (
--     SELECT id FROM (
--         SELECT id, ROW_NUMBER() OVER (
--             PARTITION BY estacion_id, route_id ORDER BY detectado_en DESC
--         ) AS posicion
--         FROM pasos_registrados
--     ) ranked
--     WHERE posicion > 10
-- );
