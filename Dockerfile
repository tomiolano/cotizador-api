FROM python:3.11-slim

# Creamos la carpeta de trabajo
WORKDIR /app

# Copiamos tus requerimientos y los instalamos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalamos el navegador invisible y todas las librerías del sistema que necesita
RUN playwright install chromium
RUN playwright install-deps chromium

# Copiamos tu archivo main.py
COPY . .

# Encendemos la API
CMD sh -c "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"
