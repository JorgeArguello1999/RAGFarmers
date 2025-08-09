# --- Ruta de ejemplo para demostrar que el servidor no está bloqueado ---
@app.get("/", tags=["General"])
async def root():
    """
    Ruta raíz para verificar que el servidor está respondiendo.
    """
    return {"status": "El servidor está en línea y respondiendo."}

