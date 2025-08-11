# Usa una imagen base oficial de Python.
# Optamos por la versión slim para reducir el tamaño de la imagen.
FROM python:3.9-slim

# Establece el directorio de trabajo dentro del contenedor.
WORKDIR /app

# Copia los archivos de requisitos e instálalos.
# Esto se hace primero para aprovechar el cache de Docker.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código de la aplicación al directorio de trabajo.
COPY . .

# Expone el puerto 8501, que es el puerto por defecto de Streamlit.
EXPOSE 8501

# Comando para ejecutar la aplicación cuando el contenedor se inicie.
# El --server.port 8501 se asegura de que Streamlit escuche en ese puerto.
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]