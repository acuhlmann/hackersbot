@echo off
echo ========================================
echo HackerNews AI Summarizer - Setup
echo ========================================
echo.

echo Step 1: Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    echo Try: python3 -m venv venv
    pause
    exit /b 1
)

echo.
echo Step 2: Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Step 3: Upgrading pip...
python -m pip install --upgrade pip

echo.
echo Step 4: Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo Step 5: Creating .env file (if it doesn't exist)...
if not exist .env (
    if exist .env.example (
        copy .env.example .env
        echo Created .env from .env.example
    ) else (
        echo .env.example not found, skipping...
    )
) else (
    echo .env already exists, skipping...
)

echo.
echo ========================================
echo Setup complete!
echo ========================================
echo.
echo Next steps:
echo 1. Make sure Ollama is running
echo 2. Download Qwen models: ollama pull qwen2.5:7b
echo 3. Activate venv: venv\Scripts\activate
echo 4. Run: python -m src.main --top-n 3
echo.
pause

