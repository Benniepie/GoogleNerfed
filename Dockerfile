FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend and frontend files
COPY main.py .
COPY static/ ./static/

# Ensure the data directory exists
RUN mkdir -p /app/data

# Run the FastAPI server using Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8069"]
