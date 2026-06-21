# Monitor Metrobús — Fase 0 + Fase 1

Esqueleto del proyecto (FastAPI + PostgreSQL/PostGIS en Docker) más el
esquema de base de datos y la carga de datos estáticos del GTFS.

## Qué incluye esta fase

**Fase 0:**
- Estructura del proyecto, configuración por variables de entorno,
  `docker-compose.yml`, endpoint `/health`.

**Fase 1 — Base de datos:**
- `app/db/schema.py`: el DDL completo (tablas `rutas`, `estaciones`,
  `ruta_estaciones`, `vehiculos_actuales`, `pasos_registrados`),
  como SQL directo — sin ORM. Con solo 5 tablas planas sin relaciones
  de herencia, SQLAlchemy no aportaba valor; `asyncpg` solo (driver
  async nativo de Postgres) es más simple de leer y depurar.
- `app/db/session.py`: pool de conexiones async (`asyncpg`) y
  `init_models()`, que crea las tablas si no existen al arrancar la app.
- `scripts/cargar_gtfs_estatico.py`: ETL que lee el zip del GTFS
  estático oficial y puebla esas tablas (UPSERT, idempotente).
- `app/services/retencion.py`: poda `pasos_registrados` a los últimos
  10 registros *por cada combinación estación+ruta* (no global), para
  no perder historial de estaciones poco transitadas.
- `docs/schema.sql`: el DDL documentado, con ejemplos de consultas
  (estación más cercana usando el índice espacial GIST, poda de
  retención).

## Desarrollo local vs. producción

En **desarrollo**, `docker-compose.yml` levanta un contenedor
`postgis/postgis` local — no necesitas cuenta en ningún lado.

En **producción**, la recomendación es [Supabase](https://supabase.com):
Postgres administrado con PostGIS disponible gratis (toggle de un
clic en el dashboard), generoso para esta escala (500 MB, tú usas
unos cuantos MB). El único punto a vigilar: los proyectos gratuitos
de Supabase se pausan tras 7 días sin actividad de base de datos —
pero el worker de la Fase 3 escribe cada 30 segundos mientras esté
corriendo, así que en la práctica el servicio se mantiene despierto
solo. El cambio entre ambos entornos es solo la variable
`DATABASE_URL` en `.env` — el código no se entera de la diferencia.

## Cómo arrancarlo

1. Copia la plantilla de entorno y rellena tus credenciales reales:

   ```bash
   cp .env.example .env
   ```

2. Levanta todo con Docker Compose:

   ```bash
   docker compose up -d --build
   ```

3. Verifica que esté vivo (esto ya debería crear las tablas vacías):

   ```bash
   curl http://localhost:8000/health
   ```

4. Copia tu zip del GTFS estático de Metrobús al contenedor y cárgalo:

   ```bash
   docker compose cp ./Metrobus_GTFS_ESTATICO.zip api:/code/Metrobus_GTFS_ESTATICO.zip
   docker compose exec api python -m scripts.cargar_gtfs_estatico /code/Metrobus_GTFS_ESTATICO.zip
   ```

   Deberías ver algo como:

   ```
   Una sola agencia encontrada: id=1339 nombre='Metrobus'. Se usara directamente.
   Rutas de Metrobus encontradas: 88
   Viajes (trips) relevantes: 44491
   Combinaciones ruta-estacion-sentido: 2085
   Estaciones distintas usadas: 381
   Rutas insertadas/actualizadas: 88
   Estaciones insertadas/actualizadas: 381
   Relaciones ruta-estacion insertadas/actualizadas: 2085
   Listo.
   ```

5. (Opcional) Inspecciona los datos cargados conectándote a
   `localhost:5432` (usuario/clave `metrobus`/`metrobus`) con DBeaver
   u otro cliente SQL.

## Siguiente paso

Fase 2: el cliente autenticado que hace login contra la API real de
Metrobús (usuario/contraseña → token) y descarga/decodifica el feed
GTFS-RT.
