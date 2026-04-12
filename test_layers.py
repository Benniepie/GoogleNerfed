from fastapi.testclient import TestClient
from main import app
import os

client = TestClient(app)

def test_layers():
    response = client.get("/api/layers")
    print(response.status_code)
    print(response.json())

test_layers()
