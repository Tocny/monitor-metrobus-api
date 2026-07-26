"""
Carga el DDLdesde el archivo schema.sql

"""

from pathlib import Path

# Ruta al archivo schema.sql (en el mismo directorio que este archivo)
_SCHEMA_PATH: Path = Path(__file__).parent / "schema.sql"

# Contenido completo del archivo SQL
DDL_SQL: str = _SCHEMA_PATH.read_text(encoding="utf-8")

# app/db/schema.py

from pathlib import Path

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _limpiar_sentencia(stmt: str) -> str:
    """
    Elimina líneas de comentario SQL y espacios sobrantes de una sentencia.

    Esta función auxiliar se utiliza para preparar las sentencias en
    SQL antes de ser ejecutadas. Elimina las líneas que comienzan con '--'
    y recorta los espacios en blanco al inicio y final.

    Args:
        stmt: Cadena de texto que contiene una o más líneas SQL.

    Returns:
        La sentencia SQL sin líneas de comentario y sin espacios iniciales/finales.
        Si después de limpiar la sentencia queda vacía, retorna una cadena vacía.

    Example:
        >>> _limpiar_sentencia("SELECT 1; -- comentario")
        'SELECT 1;'
        >>> _limpiar_sentencia("\\n  -- comentario\\nSELECT 2;\\n")
        'SELECT 2;'
    """
    lineas = [
        linea for linea in stmt.splitlines()
        if not linea.strip().startswith("--")
    ]
    return "\n".join(lineas).strip()


def get_sentencias() -> list[str]:
    """
    Lee el archivo schema.sql y devuelve una lista de sentencias SQL limpias.

    El archivo schema.sql contiene la definición completa del esquema de la base
    de datos. Al ejecutar cada sentencia aislada, se puede configurar el 
    esquema de forma segura.

    Returns:
        Lista de sentencias SQL limpias y no vacías, para ser ejecutadas
        con asyncpg.

    Example:
        >>> sentencias = get_sentencias()
        >>> len(sentencias) > 0
        True
        >>> sentencias[0].startswith("CREATE EXTENSION")
        True
    """
    sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    return [
        limpia for stmt in sql.split(";")
        if (limpia := _limpiar_sentencia(stmt))
    ]