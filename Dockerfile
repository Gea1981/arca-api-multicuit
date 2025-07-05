FROM python:3.10-slim

# Evita que Python escriba archivos .pyc en disco y que bufferice stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Zona horaria
ENV TZ=America/Argentina/Tucuman

WORKDIR /app

# Instala dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el código de la aplicación
COPY . .

# Exponemos el puerto 8000 para HTTP
EXPOSE 8000

# Healthcheck para monitorizar el contenedor via endpoint /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Arrancamos Uvicorn en modo producción
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
