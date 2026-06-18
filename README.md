# Monitor Metrobús — Fase 0

Esqueleto del proyecto: FastAPI + PostgreSQL/PostGIS corriendo en Docker,
con un endpoint `/health` para validar que todo está conectado.

## Qué incluye esta fase

- Estructura de carpetas del proyecto (`app/core`, `app/db`, `app/api`,
  `app/models`, `app/services` — estos dos últimos vacíos, listos para
  Fase 1 y Fase 2/3).
- Configuración centralizada vía variables de entorno (`app/core/config.py`),
  nunca hardcodeada.
- Conexión async a base de datos (`app/db/session.py`).
- `docker-compose.yml` con dos servicios: `api` (FastAPI) y `db`
  (PostgreSQL 16 + PostGIS 3.4).
- Endpoint `GET /health` que confirma que la app levantó y que la
  base de datos responde.

## Cómo arrancarlo

1. Copia la plantilla de entorno y rellena tus credenciales reales:

   ```bash
   cp .env.example .env
   # edita .env con tu editor de texto
   ```

2. Levanta todo con Docker Compose:

   ```bash
   docker compose up --build
   ```

3. Verifica que esté vivo:

   ```bash
   curl http://localhost:8000/health
   ```

   Deberías ver algo como:

   ```json
   {
     "status": "ok",
     "app": "Monitor Metrobus API",
     "environment": "development",
     "database_connected": true
   }
   ```

4. La documentación interactiva de la API (Swagger) queda disponible en:

   ```
   http://localhost:8000/docs
   ```

## Siguiente paso

Fase 1: cargar el GTFS estático (rutas, estaciones, trazos) dentro de
las tablas de PostgreSQL/PostGIS que arrancamos vacías en esta fase.
