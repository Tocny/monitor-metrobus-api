"""
Carga el DDL del esquema desde schema.sql (el archivo SQL real que
vive junto a este modulo, no una copia incrustada en Python).

asyncpg ejecuta archivos con varias sentencias separadas por ";" en
una sola llamada a conn.execute() cuando se invoca sin parametros
(usa el protocolo "simple query" de Postgres, que soporta multiples
sentencias) -- por eso no hace falta partir el archivo en una lista.
"""

from pathlib import Path

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"

DDL_SQL: str = _SCHEMA_PATH.read_text(encoding="utf-8")
