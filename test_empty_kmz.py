import zipfile
with zipfile.ZipFile('empty.kmz', 'w') as zf:
    zf.writestr('doc.txt', 'not a kml')
