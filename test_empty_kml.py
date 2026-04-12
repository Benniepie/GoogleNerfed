import zipfile

with zipfile.ZipFile('not_a_kmz.kmz', 'w') as zf:
    zf.writestr('doc.txt', 'no kml here')
