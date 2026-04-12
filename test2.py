import zipfile
import shutil
from pathlib import Path
import os

DATA_DIR = Path("/tmp/data")
DATA_DIR.mkdir(exist_ok=True)

with zipfile.ZipFile('test.kmz', 'w') as zf:
    zf.writestr('files/doc.kml', '<kml></kml>')

target_path = DATA_DIR / 'test.kmz'
shutil.copy('test.kmz', target_path)

safe_filename = 'test.kmz'

with zipfile.ZipFile(target_path, 'r') as zip_ref:
    kml_files = [f for f in zip_ref.namelist() if f.lower().endswith('.kml')]
    if kml_files:
        print(f"kml_files[0]: {kml_files[0]}")
        extracted_path = zip_ref.extract(kml_files[0], path="/tmp")
        print(f"extracted_path: {extracted_path}")
        kml_filename = safe_filename[:-4] + ".kml"
        final_kml_path = DATA_DIR / kml_filename
        print(f"final_kml_path: {final_kml_path}")
        shutil.move(extracted_path, final_kml_path)
        print("Success")
    else:
        print("No kml found")

print(list(DATA_DIR.iterdir()))
