const fs = require('fs');

async function doUpload() {
  const fileBuffer = fs.readFileSync('test.kmz');
  const blob = new Blob([fileBuffer], { type: 'application/vnd.google-earth.kmz' });
  const formData = new FormData();
  formData.append('files', blob, 'test.kmz');

  const response = await fetch('http://localhost:3000/api/upload', {
    method: 'POST',
    headers: {
      'Authorization': 'Basic ' + btoa('admin:changeme')
    },
    body: formData
  });

  const text = await response.text();
  console.log('Upload response:', text);

  const layersRes = await fetch('http://localhost:3000/api/layers');
  const layers = await layersRes.json();
  console.log('Layers:', layers);
}
doUpload();
