from contextlib import asynccontextmanager
from fastapi import FastAPI

from dotenv import load_dotenv
from pathlib import Path
from os import getenv
load_dotenv()

from routers.upload import router as upload_router
from routers.home import router as home_router
from routers.check import router as check_router

# Directory where uploaded files will be stored
UPLOAD_DIRECTORY = getenv("UPLOAD_DIRECTORY", "data")

# Initialize the upload directory if it doesn't exist
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager for the lifespan of the FastAPI application.
    This is used to set up resources that need to be initialized at startup.
    """
    # Initialize resources here if needed
    Path(UPLOAD_DIRECTORY).mkdir(parents=True, exist_ok=True)
    print(f"Upload file: {UPLOAD_DIRECTORY}")

    yield  # This is where the application runs

# Create the FastAPI application instance
app = FastAPI(
    title="AI-Licitaciones API",
    description="AI-powered web tool for automating construction bid analysis. Uses FastAPI, Streamlit, OCR, and NLP to extract and classify legal, technical, and financial data from PDFs, validate contractors, detect risks, and compare proposals via interactive dashboards.",
    version="1.0.0",
    lifespan=lifespan,
)

# Routes
app.include_router(home_router, prefix="/api/v1", tags=["Home"])
app.include_router(upload_router, prefix="/api/v1", tags=["Files"])
app.include_router(check_router, prefix="/api/v1", tags=["Data Check"])