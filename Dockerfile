# Imagen base ligera con Python 3.12
FROM python:3.12-slim

WORKDIR /code

# Dependencias del sistema necesarias para compilar algunos paquetes
# (asyncpg, etc.) y para geoalchemy2/postgis client libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instala dependencias de Python primero.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el codigo de la aplicacion
COPY ./app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
