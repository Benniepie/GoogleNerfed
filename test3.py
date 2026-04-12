import zipfile
import shutil
from pathlib import Path
import os
import tempfile

DATA_DIR = Path("/tmp/data2")
DATA_DIR.mkdir(exist_ok=True)

with zipfile.ZipFile('test.kmz', 'w') as zf:
    zf.writestr('doc.kml', '<kml></kml>')
    zf.writestr('images/icon.png', 'fake image data')

target_path = DATA_DIR / 'test.kmz'
shutil.copy('test.kmz', target_path)

safe_filename = 'test.kmz'

try:
    with zipfile.ZipFile(target_path, 'r') as zip_ref:
        kml_files = [f for f in zip_ref.namelist() if f.lower().endswith('.kml')]
        if kml_files:
            extracted_path = zip_ref.extract(kml_files[0], path="/tmp")
            kml_filename = safe_filename[:-4] + ".kml"
            final_kml_path = DATA_DIR / kml_filename
            shutil.move(extracted_path, final_kml_path)
            print("Successfully extracted and moved")
except Exception as e:
    print(f"Exception: {e}")

print(list(DATA_DIR.iterdir()))
