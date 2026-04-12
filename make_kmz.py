import zipfile

with zipfile.ZipFile('test_no_dir.kmz', 'w') as zf:
    zf.writestr('doc.kml', '<kml></kml>')

with zipfile.ZipFile('test_dir.kmz', 'w') as zf:
    zf.writestr('files/doc.kml', '<kml></kml>')
