from fastapi.testclient import TestClient
from main import app
import os

client = TestClient(app)

def test_upload_kmz():
    with open("test.kmz", "rb") as f:
        response = client.post(
            "/api/upload",
            files={"files": ("My test.kmz", f, "application/vnd.google-earth.kmz")},
            auth=("admin", "changeme")
        )
    print(response.status_code)
    print(response.json())

test_upload_kmz()
