import os
import shutil
import zipfile
from pathlib import Path
from fastapi import FastAPI, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Enable CORS just in case
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path("/app/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

@app.get("/api/layers")
async def get_layers():
    """Returns a list of all KML files in the data directory."""
    files = []
    for f in DATA_DIR.iterdir():
        if f.is_file() and f.suffix.lower() == '.kml':
            files.append(f.name)
    return {"layers": sorted(files)}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Handles KML and KMZ uploads, automatically extracting KMZ to KML."""
    file_ext = file.filename.lower().split('.')[-1]
    safe_filename = file.filename.replace(" ", "_")
    target_path = DATA_DIR / safe_filename

    # Save the uploaded file temporarily
    with open(target_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    if file_ext == 'kmz':
        try:
            # Extract KML from the KMZ archive
            with zipfile.ZipFile(target_path, 'r') as zip_ref:
                kml_files = [f for f in zip_ref.namelist() if f.lower().endswith('.kml')]
                if kml_files:
                    extracted_path = zip_ref.extract(kml_files[0], path="/tmp")
                    kml_filename = safe_filename[:-4] + ".kml"
                    final_kml_path = DATA_DIR / kml_filename
                    shutil.move(extracted_path, final_kml_path)
            # Remove the original KMZ file
            target_path.unlink(missing_ok=True)
            return {"message": "KMZ extracted and saved successfully", "filename": kml_filename}
        except zipfile.BadZipFile:
            target_path.unlink(missing_ok=True)
            return {"error": "Invalid KMZ file"}
            
    return {"message": "KML saved successfully", "filename": safe_filename}


@app.delete("/api/layers/{filename}")
async def delete_layer(filename: str):
    """Safeguards the file by renaming it with a .deleted extension."""
    file_path = DATA_DIR / filename
    if file_path.exists() and file_path.is_file():
        # Rename instead of permanent deletion
        file_path.rename(file_path.with_suffix('.kml.deleted'))
        return {"message": "Layer archived"}
    return {"error": "File not found"}

# Serve the data directory so the frontend can fetch the KML files
app.mount("/data", StaticFiles(directory="/app/data"), name="data")

# Serve the frontend HTML
@app.get("/")
async def serve_frontend():
    return FileResponse("static/index.html")

# Serve any other static assets if needed
app.mount("/", StaticFiles(directory="static"), name="static")
