# Monitor Metrobús — Fase 3

## Qué se construyó

La Fase 3 implementa el worker de polling en background y la
refactorización completa del proyecto al patrón
Controller → Service → Repository → Entity.

### Archivos nuevos

**Entidades** (`app/entities/`) — contratos de datos entre capas,
definidos con Pydantic:
- `ruta.py` → `Ruta`
- `estacion.py` → `Estacion`
- `vehiculo.py` → `Vehiculo` (del feed) y `VehiculoActual` (de la BD)
- `paso.py` → `PasoRegistrado`

**Repositories** (`app/repositories/`) — solo acceso a datos, sin
lógica de negocio. Reciben una conexión asyncpg y devuelven entidades:
- `estaciones_repository.py` → `get_estaciones_de_ruta`, `get_estacion_cercana`
- `vehiculos_repository.py` → `get_vehiculo`, `upsert_vehiculo`
- `pasos_repository.py` → `insertar_paso`, `get_ultimo_paso`, `podar_pasos`

**Services nuevos** (`app/services/`):
- `geo.py` → `distancia_metros()`: utilidad pura Haversine, sin
  dependencias del proyecto ni riesgo de imports circulares.
- `worker.py` → orquesta el ciclo de polling. No contiene SQL ni
  lógica HTTP — delega todo a repositories y a metrobus_client.

### Archivos refactorizados

- `app/services/metrobus_client.py` → simplificado: sin clases,
  estado en variables de módulo, devuelve `list[Vehiculo]` en vez
  de `list[dict]`.
- `app/api/routes/debug.py` → usa `model_dump()` para serializar
  entidades `Vehiculo` en la respuesta HTTP.
- `app/main.py` → el lifespan ahora arranca y detiene el worker.

### Archivos eliminados

- `app/services/retencion.py` → absorbido por `pasos_repository.py`
  como `podar_pasos()`, llamado automáticamente dentro de
  `insertar_paso()`.

## Cómo funciona el worker

Cada 30 segundos (configurable vía `POLLING_INTERVAL_SECONDS` en
`.env`):

1. Llama a `metrobus_client.obtener_vehiculos_actuales()` que valida
   contra `partnerValidation` si las URLs prefirmadas de S3 están por
   expirar (caducan cada 10 minutos según el manual de SONDA), y
   descarga + decodifica el feed GTFS-RT.

2. Por cada uno de los ~836 vehículos activos, consulta las estaciones
   de su ruta (con cache por ciclo para no repetir el mismo SELECT por
   cada camión de la misma ruta) y calcula si está dentro del radio de
   alguna estación usando Haversine (`app/services/geo.py`).

3. Si el vehículo estaba FUERA del radio de una estación y ahora está
   DENTRO → paso confirmado: inserta en `pasos_registrados` y poda
   la tabla a los últimos 10 registros por combinación estación+ruta.

4. Sobreescribe `vehiculos_actuales` con la posición nueva (UPSERT).
   Esta tabla nunca crece — siempre tiene una fila por vehículo activo.

## Verificar que está funcionando

```bash
# Vehículos activos en la BD
docker compose exec db psql -U metrobus -d metrobus -c \
  "SELECT COUNT(*) FROM vehiculos_actuales;"

# Últimos pasos detectados
docker compose exec db psql -U metrobus -d metrobus -c \
  "SELECT p.label, e.nombre, p.route_id, p.detectado_en
   FROM pasos_registrados p
   JOIN estaciones e ON e.stop_id = p.estacion_id
   ORDER BY p.detectado_en DESC
   LIMIT 10;"
```

## Siguiente paso

Fase 4 — Endpoints REST:
- `GET /estaciones/cercana?lat=&lon=` (usando índice GIST de PostGIS)
- `GET /estaciones/{stop_id}/ultimo-paso?route_id=`
- `GET /mapa/geojson` (líneas + estaciones para Mapbox)