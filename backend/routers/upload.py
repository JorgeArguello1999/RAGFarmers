from fastapi import HTTPException
from fastapi import UploadFile
from fastapi import APIRouter
from fastapi import status
from fastapi import File

from typing import List
from pathlib import Path
import aiofiles
import os

# Constants
UPLOAD_DIRECTORY = os.getenv("UPLOAD_DIRECTORY", "data") 

# Router for file upload operations
router = APIRouter()

# API endpoint to upload multiple PDF files
@router.post(
    "/upload-pdfs/",
    summary="Subir uno o varios archivos PDF",
    tags=["Files"],
    status_code=status.HTTP_201_CREATED
)
async def upload_multiple_pdfs(files: List[UploadFile] = File(..., description="Lista de archivos PDF a subir")):
    """
    Sube uno o más archivos PDF al servidor.

    Esta ruta está diseñada para ser eficiente y no bloqueante:
    - **Procesamiento asíncrono**: Libera el hilo principal del servidor para atender otras peticiones.
    - **Lectura en fragmentos**: Lee y escribe los archivos por partes (chunks) para manejar archivos grandes sin agotar la memoria RAM.
    - **Validación de tipo**: Rechaza archivos que no tengan el `Content-Type` de 'application/pdf'.

    **Retorna**:
    - Un objeto JSON confirmando el número de archivos subidos y sus nombres.
    - Un error 400 si algún archivo no es un PDF.
    - Un error 500 si ocurre un problema al guardar un archivo.
    """
    uploaded_filenames = []

    for file in files:
        # **1. Validación del tipo de archivo**
        if file.content_type != "application/pdf":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El archivo '{file.filename}' no es un PDF válido. Se recibió el tipo: {file.content_type}",
            )

        # **2. Preparación de la ruta de destino**
        # Se usa `os.path.basename` por seguridad, para evitar ataques de path traversal.
        sanitized_filename = os.path.basename(file.filename)
        destination_path = Path(UPLOAD_DIRECTORY) / sanitized_filename

        try:
            # **3. Escritura asíncrona del archivo en fragmentos**
            async with aiofiles.open(destination_path, 'wb') as out_file:
                while content := await file.read(1024 * 1024):  # Lee en chunks de 1MB
                    await out_file.write(content)
            uploaded_filenames.append(sanitized_filename)
        except Exception as e:
            # Si algo sale mal durante la escritura, se lanza un error.
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"No se pudo guardar el archivo '{file.filename}'. Error: {e}",
            )
        finally:
            # Es buena práctica cerrar el archivo para liberar recursos.
            await file.close()

    return {
        "message": f"Se han subido exitosamente {len(uploaded_filenames)} archivos PDF.",
        "uploaded_files": uploaded_filenames,
    }

