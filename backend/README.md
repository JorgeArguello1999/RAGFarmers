# Backend Documentation

This backend is built with **FastAPI** and provides RESTful APIs for document upload, storage, and processing, focusing on PDF files for tender analysis. It uses **Redis** for fast file storage and metadata management.

---

## 📁 Directory Structure

```
backend/
├── .env                  # Environment variables for backend and Redis
├── Dockerfile            # Dockerfile for FastAPI backend
├── main.py               # FastAPI application entry point
├── requirements.txt      # Python dependencies
├── data/                 # Directory for uploaded files (created at runtime)
├── database/
│   ├── redis.conf        # Redis configuration file
│   └── redis.py          # Async Redis client and file storage logic
├── routers/
│   ├── home.py           # Root API endpoint (health check)
│   ├── upload.py         # PDF upload API endpoint
│   └── check.py          # Processing status endpoints
├── schemas/
│   └── File.py           # Custom exception for file upload errors
└── utils/
    └── file.py           # File validation and saving utilities
```

---

## ⚙️ Environment Variables

Configure the backend using a `.env` file or pass them as environment variables to the Docker container:

```
UPLOAD_DIRECTORY=data
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=devpass123
```

---

## 🚀 Main Components

- **main.py**  
  FastAPI app initialization, router registration, and upload directory setup.

- **routers/upload.py**  
  `/api/v1/files/upload-pdfs` endpoint for uploading one or more PDF files.  
  - Validates file type and size.
  - Assigns a unique UUID to each file.
  - Stores file content and metadata in Redis.

- **routers/home.py**  
  `/api/v1/` root endpoint for health checks.

- **routers/check.py**  
  `/api/v1/check/status` and `/api/v1/check/start` endpoints for checking and updating the processing status in Redis.

- **database/redis.py**  
  Async Redis client and logic for storing PDF content and metadata using a transaction.  
  Also manages the processing status flag.

- **utils/file.py**  
  - `sanitize_filename`: Prevents path traversal and invalid characters.
  - `validate_pdf_file`: Checks file type and size.
  - `save_file_async`: Asynchronous file saving utility.

- **schemas/File.py**  
  Custom exception for file upload errors.

- **database/redis.conf**  
  Redis configuration (password, memory policy, etc).

- **Dockerfile**  
  Dockerfile for running the FastAPI backend.

---

## 📝 API Endpoints

### Health Check

- **GET** `/api/v1/`
  - Returns server status.

### Upload PDF Files

- **POST** `/api/v1/files/upload-pdfs`
  - Accepts one or more PDF files.
  - Validates each file (type and size).
  - Stores each file in Redis with metadata and a unique ID.
  - Returns a list of uploaded file IDs and original filenames.
  - Handles partial and total upload failures.

### Processing Status

- **GET** `/api/v1/check/status`
  - Returns the current processing status from Redis.

- **POST** `/api/v1/check/start`
  - Sets the processing status to `True` in Redis (used to manually trigger processing).

---

## 🐳 Running with Docker

### 1. Run Redis Server (with custom config)

```
cd backend/database
# Use the provided Dockerfile in the project root for Redis
# (Make sure you are in the correct directory with the Redis Dockerfile)
docker build -t ragformers-redis -f ../Dockerfile .
docker run -d -p 6379:6379 --name redis-server ragformers-redis
```

### 2. Run FastAPI Backend

Build the backend image:

```
cd backend
# Build the FastAPI backend Docker image
# (This uses backend/Dockerfile)
docker build -t ragformers-backend .
```

Run the backend container (set environment variables as needed):

```
docker run -d \
  --name ragformers-backend \
  --env UPLOAD_DIRECTORY=data \
  --env REDIS_HOST=<redis_host> \
  --env REDIS_PORT=6379 \
  --env REDIS_PASSWORD=devpass123 \
  -p 8000:8000 \
  ragformers-backend
```

- Replace `<redis_host>` with the hostname or IP of your Redis server (e.g., `host.docker.internal` if running Redis on your host machine).
- The backend will be available at [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 📦 Install Dependencies (for local development)

```
cd backend
pip install -r requirements.txt
```

---

## ▶️ Start the FastAPI Server (for local development)

```
uvicorn main:app --reload
```

---

## 🧪 Testing the API

You can test the API using [http://localhost:8000/docs](http://localhost:8000/docs) (FastAPI Swagger UI).

---

## 📄 Notes

- Uploaded files are stored in Redis and not on disk by default.
- The `data/` directory is created at runtime for temporary storage if needed.
- The backend is stateless and designed for scalability.
- Processing status is managed via Redis and can be checked or updated through dedicated endpoints.

---