import requests
import json
import base64

def upload(filename):
    with open(filename, 'rb') as f:
        auth = base64.b64encode(b"admin:changeme").decode("utf-8")
        res = requests.post(
            'http://localhost:3000/api/upload',
            files={'files': (filename, f, 'application/vnd.google-earth.kmz')},
            headers={'Authorization': f'Basic {auth}'}
        )
        print(f"Upload {filename}:", res.status_code, res.text)

if __name__ == "__main__":
    upload('test_no_dir.kmz')
    upload('test_dir.kmz')
    res = requests.get('http://localhost:3000/api/layers')
    print("Layers:", res.status_code, res.json())
