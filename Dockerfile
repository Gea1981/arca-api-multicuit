FROM python:3.10-slim

# Evita archivos .pyc y forzar flushing de logs
ENV PYTHONDONTWRITEBYTECODE=1  
ENV PYTHONUNBUFFERED=1  

# Zona horaria (requiere tzdata instalado)
ENV TZ=America/Argentina/Tucuman  
ARG DEBIAN_FRONTEND=noninteractive  

WORKDIR /app

# Ajuste de OpenSSL para aceptar DH keys débiles
RUN sed -i 's/CipherString = DEFAULT@SECLEVEL=2/CipherString = DEFAULT@SECLEVEL=1/' /etc/ssl/openssl.cnf

# Instalación de utilidades y zona horaria
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      curl \  
      tzdata && \
    rm -rf /var/lib/apt/lists/*

# Copia dependencias primero para caching
COPY requirements.txt .

# Instalación de dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia el código de la aplicación
COPY . .

# Crea y usa un usuario sin privilegios root
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

# Puerto de la aplicación
EXPOSE 8000

# Healthcheck para monitorizar /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Arranque de Uvicorn en producción
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
