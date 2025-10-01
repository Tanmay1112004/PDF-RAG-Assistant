#!/bin/bash

# Install system dependencies for PDF processing
apt-get update
apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgl1-mesa-glx \
    poppler-utils \
    tesseract-ocr \
    libreoffice

# Install Python packages
pip install -r requirements.txt

echo "✅ All dependencies installed successfully!"