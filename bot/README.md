# RAGFormers Backend Worker - Docker Deployment Guide

Este instructivo explica cómo construir y ejecutar el backend worker de RAGFormers usando el `Dockerfile` incluido.

## Prerrequisitos
- Tener [Docker](https://docs.docker.com/get-docker/) instalado.
- (Opcional) Un archivo `.env` con tus variables de entorno (por ejemplo, credenciales de Redis) en el directorio raíz del proyecto o en `backend/`.

## Variables de Entorno Necesarias
Asegúrate de definir las siguientes variables en tu archivo `.env` o en la configuración de Docker:

- `REDIS_HOST` (por defecto: `localhost`)
- `REDIS_PORT` (por defecto: `6379`)
- `REDIS_PASSWORD` (por defecto: `devpass123`)
- `RELOAD_URL` (por defecto: `http://localhost:8000/api/v1/llm/reload-docs`)
- Cualquier otra variable que tu backend requiera

Ejemplo de `.env`:
```
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=devpass123
RELOAD_URL="http://localhost:8000/api/v1/llm/reload-docs"  
```

## Construir la Imagen Docker

Desde la raíz del proyecto, ejecuta:

```bash
# Construir la imagen del backend worker
docker build -t ragformers-backend-worker .
```

## Ejecutar el Contenedor

```bash
docker run -d \
  --name ragformers-backend-worker \
  -p 8000:8000 \
  --env-file .env \
  ragformers-backend-worker
```

- La API estará disponible en: [http://localhost:8000/docs](http://localhost:8000/docs)
- Cambia la ruta de `--env-file` si tu `.env` está en otra ubicación.

## Comandos Útiles
- **Detener el contenedor:**
  ```bash
  docker stop ragformers-backend-worker
  ```
- **Eliminar el contenedor:**
  ```bash
  docker rm ragformers-backend-worker
  ```
- **Ver logs:**
  ```bash
  docker logs -f ragformers-backend-worker
  ```

## Notas
- Asegúrate de que Redis y otros servicios requeridos sean accesibles desde el contenedor.
- Para producción, considera usar un gestor de procesos (como Gunicorn) y una gestión adecuada de variables de entorno.

---

**Desarrollado por RAGFormers 🚀**
