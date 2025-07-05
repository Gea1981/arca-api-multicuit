FROM python:3.10-slim

WORKDIR /app

# Instalar herramientas del sistema necesarias para compilar dependencias
# Usamos --no-install-recommends para una imagen más ligera y limpiamos la caché de apt
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    build-essential \
    libxml2-dev \
    libxmlsec1-dev \
    libxmlsec1-openssl \
    pkg-config \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Copiamos solo el archivo de dependencias para aprovechar el cache de Docker
COPY requirements.txt .

# Instalación de dependencias Python
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Ahora copiamos el resto del código
COPY . .

# Creamos un usuario no-root para correr la aplicación
RUN useradd -m appuser
USER appuser

# Exponemos el puerto en el que corre Uvicorn
EXPOSE 8000

# Comando por defecto
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
