from fastapi import APIRouter, HTTPException
import json 
from pathlib import Path

JSON_FILE_PATH = Path("output.json")

router = APIRouter(prefix="/llm", tags=["LLM Dashboard"])

@router.get("/dashboard")
def get_dashboard_data():
    """
    Lee y devuelve el contenido del archivo JSON del dashboard.
    """
    try:
        if not JSON_FILE_PATH.exists():
            raise HTTPException(status_code=404, detail=f"Archivo no encontrado: {JSON_FILE_PATH}")
            
        with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al leer el archivo JSON: {e}")
