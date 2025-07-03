FROM python:3.10-slim

WORKDIR /app

# Instalar herramientas del sistema necesarias
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    build-essential \
    libxml2-dev \
    libxmlsec1-dev \
    libxmlsec1-openssl \
    pkg-config \
  && apt-get clean

# Copiamos todo el código al contenedor
COPY . .

# Instalación de dependencias Python
RUN pip install --upgrade pip \
  && pip install -r requirements.txt

# Exponemos el puerto en el que corre Uvicorn
EXPOSE 8000

# Comando por defecto
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
