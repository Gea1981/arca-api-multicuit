FROM python:3.10-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Exponemos el puerto 8000 para HTTP
EXPOSE 8000

# Arrancamos Uvicorn en 0.0.0.0 para que sea accesible desde fuera
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]