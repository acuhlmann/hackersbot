# HackerNews AI Summarizer Agent

A multi-agent Python application that scrapes Hacker News, filters AI-related topics, and generates summaries using local Qwen models via Ollama.

## Features

- Scrapes top N articles from Hacker News
- Extracts and parses article comments
- Filters AI-related topics (optional)
- Generates summaries using local LLM models (Qwen via Ollama)
- Saves summaries in multiple formats (JSON, Markdown)
- Console and file output support

## Prerequisites

- Python 3.9+
- Ollama installed and running locally
- Qwen models downloaded in Ollama (e.g., `qwen2.5:7b`, `qwen2.5:14b`)

## Setup

### Step 1: Create Virtual Environment

**Important:** Always create and activate a virtual environment before installing dependencies!

Navigate to the project directory:
```bash
cd hackersbot
```

Create a virtual environment:
```bash
python -m venv venv
```

If you have multiple Python versions, you may need to specify:
```bash
python3 -m venv venv
# or
py -3.9 -m venv venv  # Windows with Python Launcher
```

### Step 2: Activate Virtual Environment

**Windows (PowerShell):**
```powershell
venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
venv\Scripts\activate.bat
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

**Verify activation:** You should see `(venv)` at the beginning of your command prompt.

### Step 3: Install Dependencies

With the virtual environment activated:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Configure Environment (Optional)

Create a `.env` file for custom configuration:
```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

Edit `.env` if you need to change Ollama settings (defaults work for most setups).

### Step 5: Setup Ollama Models

Ensure Ollama is running and download Qwen models:
```bash
# Check if Ollama is running
ollama list

# Download Qwen models
ollama pull qwen2.5:7b
ollama pull qwen2.5:14b  # Optional, for better summaries
```

**Note:** The first time you run the app, it will download models if they're not already available.

## Usage

### Basic Usage (Top 3 Articles)

```bash
python -m src.main --top-n 3
```

### With AI Filtering

```bash
python -m src.main --top-n 30 --filter-ai
```

### Output Options

```bash
# Console only
python -m src.main --top-n 3 --output-format console

# File only
python -m src.main --top-n 3 --output-format file

# Both console and file (default)
python -m src.main --top-n 3 --output-format both
```

## Output

Summaries are saved in the `outputs/` directory with timestamps:
- `outputs/YYYY-MM-DD_HH-MM-SS_summary.json`
- `outputs/YYYY-MM-DD_HH-MM-SS_summary.md`

## Architecture

The application uses a multi-agent architecture:
- **Scraper Agent**: Fetches and parses Hacker News articles and comments
- **Filter Agent**: Identifies AI-related topics
- **Summarizer Agent**: Generates summaries using Qwen models via Ollama

## Configuration

Edit `.env` to customize:
- Ollama base URL (default: http://localhost:11434)
- Model names for different tasks

## License

MIT

