# Backend Documentation

This backend is built with **FastAPI** and provides RESTful APIs for document upload, storage, and processing, focusing on PDF files for tender analysis. It uses **Redis** for fast file storage and metadata management.

---

## 📁 Directory Structure

```
backend/
├── .env                  # Environment variables for backend and Redis
├── Dockerfile            # Dockerfile for Redis service
├── main.py               # FastAPI application entry point
├── requirements.txt      # Python dependencies
├── selenium.ipynb        # Jupyter notebook for Selenium-based scraping (demo/utility)
├── data/                 # Directory for uploaded files (created at runtime)
├── database/
│   ├── redis.conf        # Redis configuration file
│   └── redis.py          # Async Redis client and file storage logic
├── routers/
│   ├── home.py           # Root API endpoint (health check)
│   └── upload.py         # PDF upload API endpoint
├── schemas/
│   └── File.py           # Custom exception for file upload errors
└── utils/
    └── file.py           # File validation and saving utilities
```

---

## ⚙️ Environment Variables

Configure the backend using a `.env` file:

```bash
UPLOAD_DIRECTORY=data
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=devpass123
```

---

## 🚀 Main Components

- **[main.py](main.py)**  
  FastAPI app initialization, router registration, and upload directory setup.

- **[routers/upload.py](routers/upload.py)**  
  `/api/v1/files/upload-pdfs` endpoint for uploading one or more PDF files.  
  - Validates file type and size.
  - Assigns a unique UUID to each file.
  - Stores file content and metadata in Redis.

- **[routers/home.py](routers/home.py)**  
  `/api/v1/` root endpoint for health checks.

- **[database/redis.py](database/redis.py)**  
  Async Redis client and logic for storing PDF content and metadata using a transaction.

- **[utils/file.py](utils/file.py)**  
  - `sanitize_filename`: Prevents path traversal and invalid characters.
  - `validate_pdf_file`: Checks file type and size.
  - `save_file_async`: Asynchronous file saving utility.

- **[schemas/File.py](schemas/File.py)**  
  Custom exception for file upload errors.

- **[database/redis.conf](database/redis.conf)**  
  Redis configuration (password, memory policy, etc).

- **[Dockerfile](Dockerfile)**  
  Dockerfile for running a Redis server with custom configuration.

---

## 📝 API Endpoints

### Health Check

- **GET** `/api/v1/`
  - Returns server status.

### Upload PDF Files

- **POST** `/api/v1/files/upload-pdfs`
  - Accepts one or more PDF files.
  - Stores each file in Redis with metadata.
  - Returns a list of uploaded file IDs and original filenames.

---

## 🐳 Running with Docker

To run the Redis server with the provided configuration:

```bash
cd backend
docker build -t ragformers-redis .
docker run -d -p 6379:6379 --name redis-server ragformers-redis
```

---

## 📦 Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

---

## ▶️ Start the FastAPI Server

```bash
uvicorn main:app --reload
```

---

## 🧪 Testing the API

You can test the API using [http://localhost:8000/docs](http://localhost:8000/docs) (FastAPI Swagger UI).

---

## 📄 Notes

- Uploaded files are stored in Redis and not on disk by default.
- The `data/` directory is created at runtime for temporary storage if needed.
- The backend is designed to be stateless and scalable.

---