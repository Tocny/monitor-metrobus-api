# Imagen base ligera con Python 3.12
FROM python:3.12-slim

WORKDIR /code

# Dependencias del sistema -- de respaldo por si pip necesita compilar
# asyncpg en alguna plataforma sin wheel precompilado (normalmente no
# hace falta en linux x86_64, pero no cuesta nada tenerlo).
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instala dependencias de Python primero (mejor cache de capas Docker:
# si solo cambia el codigo de app/, esta capa no se reconstruye)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el codigo de la aplicacion
COPY ./app ./app
COPY ./scripts ./scripts

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
