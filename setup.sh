#!/bin/bash

# Exit on any error
set -e

echo "========================================="
echo " ATP-Maps Environment Setup Script"
echo "========================================="

echo "[1/7] Checking for system package manager (apt-get)..."
if ! command -v apt-get &> /dev/null; then
    echo "Warning: apt-get not found. This script assumes a Debian/Ubuntu-based system."
    echo "Please manually install equivalent system dependencies:"
    echo "  git build-essential python3-dev libsuitesparse-dev libgdal-dev"
else
    echo "Installing system dependencies (requires sudo)..."
    sudo apt-get update
    sudo apt-get install -y \
        git \
        build-essential \
        python3-dev \
        libsuitesparse-dev \
        libgdal-dev
fi

echo ""
echo "[2/7] Creating Python virtual environment (venv)..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Created virtual environment 'venv'."
else
    echo "Virtual environment 'venv' already exists."
fi

echo ""
echo "[3/7] Activating virtual environment..."
source venv/bin/activate

echo ""
echo "[4/7] Exporting GDAL environment variables..."
export CPLUS_INCLUDE_PATH=/usr/include/gdal
export C_INCLUDE_PATH=/usr/include/gdal
# Also append to venv/bin/activate so it persists when users manually activate
if ! grep -q "CPLUS_INCLUDE_PATH=/usr/include/gdal" venv/bin/activate; then
    echo 'export CPLUS_INCLUDE_PATH=/usr/include/gdal' >> venv/bin/activate
    echo 'export C_INCLUDE_PATH=/usr/include/gdal' >> venv/bin/activate
fi

echo ""
echo "[5/7] Installing Python dependencies..."
# Upgrade pip first
pip install --upgrade pip

# Triangle dependency must be installed from git
echo "Installing triangle dependency..."
pip install git+https://github.com/drufat/triangle.git

echo "Installing requirements from requirements.txt..."
pip install -r requirements.txt

echo ""
echo "[6/7] Installing Playwright dependencies..."
playwright install chromium --with-deps

echo ""
echo "[7/7] Setting up data directory and environment variables..."
mkdir -p data
echo "Created 'data' directory."

if [ ! -f ".env" ]; then
    cat << EOF > .env
# ATP-Maps Environment Variables Template
PORT=8080
CONTAINERSUFFIX=dev
AIS_API_KEY=your_ais_stream_api_key_here
FIRMS_API_KEY=your_firms_api_key_here
EOF
    echo "Created template '.env' file."
else
    echo "'.env' file already exists. Skipping creation."
fi

echo "========================================="
echo " Setup Complete!"
echo "========================================="
echo "To start working, run:"
echo "  source venv/bin/activate"
echo "  uvicorn main:app --reload --port 8000"
echo ""
