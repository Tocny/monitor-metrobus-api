"""
Carga el DDLdesde el archivo schema.sql

"""

from pathlib import Path

# Ruta al archivo schema.sql (en el mismo directorio que este archivo)
_SCHEMA_PATH: Path = Path(__file__).parent / "schema.sql"

# Contenido completo del archivo SQL
DDL_SQL: str = _SCHEMA_PATH.read_text(encoding="utf-8")