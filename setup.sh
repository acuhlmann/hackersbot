#!/bin/bash

echo "========================================"
echo "HackerNews AI Summarizer - Setup"
echo "========================================"
echo ""

echo "Step 1: Creating virtual environment..."
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create virtual environment"
    exit 1
fi

echo ""
echo "Step 2: Activating virtual environment..."
source venv/bin/activate

echo ""
echo "Step 3: Upgrading pip..."
python -m pip install --upgrade pip

echo ""
echo "Step 4: Installing dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi

echo ""
echo "Step 5: Creating .env file (if it doesn't exist)..."
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "Created .env from .env.example"
    else
        echo ".env.example not found, skipping..."
    fi
else
    echo ".env already exists, skipping..."
fi

echo ""
echo "========================================"
echo "Setup complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your DEEPSEEK_API_KEY"
echo "2. Activate venv: source venv/bin/activate"
echo "3. Run: python -m src.main --top-n 3"
echo ""
