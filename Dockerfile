--- a/Dockerfile
+++ b/Dockerfile
@@
 FROM python:3.10-slim

 WORKDIR /app

-# Instalar herramientas necesarias del sistema
-RUN apt-get update && apt-get install -y \
-    gcc \
-    libpq-dev \
-    build-essential \
-    libxml2-dev \
-    libxmlsec1-dev \
-    libxmlsec1-openssl \
-    pkg-config \
-    && apt-get clean
+# Instalar herramientas del sistema (incluye openssl para smime)
+RUN apt-get update && apt-get install -y \
+    openssl \
+    gcc \
+    libpq-dev \
+    build-essential \
+    libxml2-dev \
+    libxmlsec1-dev \
+    libxmlsec1-openssl \
+    pkg-config \
+ && rm -rf /var/lib/apt/lists/*

+# Crear carpetas para los certificados y los comprobantes
+RUN mkdir -p /app/certs /app/comprobantes

 COPY . .

 # Instalación de dependencias Python
 RUN pip install --upgrade pip && pip install -r requirements.txt

 EXPOSE 8000

 CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
