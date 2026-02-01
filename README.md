# HackerNews AI Summarizer Agent

A multi-agent Python application that scrapes Hacker News, filters AI-related topics, and generates summaries using DeepSeek's cloud API.

## Features

- Scrapes top N articles from Hacker News
- Extracts and parses article comments
- Filters AI-related topics (optional)
- Uses DeepSeek API for AI-powered summaries
- **Telegram Bot** for mobile access 📱
- Saves summaries in multiple formats (JSON, Markdown)
- Console and file output support

## Prerequisites

- Python 3.9+
- DeepSeek API key from https://platform.deepseek.com
- **For Telegram Bot (optional):**
  - Telegram Bot Token from @BotFather

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

### Step 4: Configure Environment

Create a `.env` file for your API key:
```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

Edit `.env` and add your DeepSeek API key:

```bash
# Deepseek API Configuration
DEEPSEEK_API_KEY=your-api-key-here

# Optional: Specify which model to use (default: deepseek-chat)
# DEEPSEEK_MODEL=deepseek-chat
```

Get your API key from: https://platform.deepseek.com

**Note:** The `.env` file is automatically loaded when you run the application. In production (e.g., GitHub Actions, Docker), environment variables are typically injected by the system.

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

## 📱 Telegram Bot

Access your HN summaries from anywhere via Telegram!

### Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) on Telegram
2. Copy the bot token
3. Set environment variables:
   ```bash
   export TELEGRAM_BOT_TOKEN=your-bot-token
   export DEEPSEEK_API_KEY=your-deepseek-key
   ```

### Run the Bot

```bash
python -m src.telegram_bot
```

### Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and help |
| `/summary` | Get top 3 articles summarized |
| `/summary 5` | Get top 5 articles summarized |
| `/ai` | Get AI-related articles only |
| `/ai 20` | Scan top 20 for AI articles |
| `/help` | Show help message |

## 🌐 Web UI

A beautiful web interface to browse and view HackerNews summaries with manual refresh capability.

### Running the Web Server Locally

1. **Make sure dependencies are installed:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the web server:**
   ```bash
   python serve.py
   ```
   
   Or specify a custom port:
   ```bash
   python serve.py 8080
   ```

3. **Open your browser:**
   - Default URL: http://localhost:8000
   - Or use the port you specified

### Web UI Features

- **Browse historical summaries** - View all past summaries in the sidebar
- **Manual refresh** - Click the "🔄 Refresh Summary" button to generate a new summary
- **Rate limiting** - Prevents refreshing more than once per hour
- **Local time display** - All refresh times shown in your local timezone
- **Real-time status** - See when the last refresh occurred and current refresh status

### Environment Variables

You can configure the server with environment variables:

```bash
# Set custom port (default: 8000)
export PORT=8080

# Set bind address (default: 0.0.0.0 for Docker, localhost for local)
export BIND_ADDRESS=localhost

# Set your DeepSeek API key
export DEEPSEEK_API_KEY=your-api-key-here
```

### Docker

You can also run the web server in Docker:

```bash
docker-compose up
```

This will start the web server on port 8000.

### Reverse proxy (production)

When putting the app behind nginx or another reverse proxy, **proxy all paths** to the backend so the web UI can load summaries and call APIs:

- **`/`** – HTML and assets
- **`/summaries/`** – JSON summary files and `index.json`
- **`/api/`** – API endpoints (status, refresh, adhoc-summaries, etc.)

Example nginx location block (proxy to container on `127.0.0.1:18080`):

```nginx
location / {
    proxy_pass http://127.0.0.1:18080;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    # For SSE (refresh stream)
    proxy_buffering off;
    proxy_read_timeout 86400s;
    proxy_send_timeout 86400s;
}
```

If the app is served from a subpath (e.g. `https://example.com/hn/`), the web UI detects it and requests `/hn/summaries` and `/hn/api/...`; ensure the proxy forwards that prefix to the backend.

## 🔄 GitHub Actions (No Server Needed!)

You can run the summarizer directly from GitHub without any server!

### Manual Run (Ad-hoc)

1. Go to your repo → **Actions** tab
2. Select **"HackerNews Summary"** workflow
3. Click **"Run workflow"**
4. Choose options:
   - Number of articles (3, 5, or 10)
   - Filter AI-only articles
   - Save to repo
5. Click **"Run workflow"**

After it completes, click on the run to see the summary in the **Job Summary** section!

### Automatic Triggers

| Trigger | When | Default Behavior |
|---------|------|------------------|
| **Scheduled** | Daily at 8 AM UTC | Summarizes top 5, saves to `outputs/` |
| **PR Merge** | After merging to main | Summarizes top 5, saves to `outputs/` |
| **Manual** | On-demand | Your choice of options |

### Where to Find Results

1. **Job Summary** - Click on any workflow run to see the formatted summary
2. **Artifacts** - Download MD/JSON files from the workflow run
3. **Repository** - If "save to repo" is enabled, files are in `summaries/` folder

### Required Secrets

Make sure you've added `DEEPSEEK_API_KEY` in:
**Settings → Secrets and variables → Actions → New repository secret**

## Output

Summaries are saved in the `outputs/` directory with timestamps:
- `outputs/YYYY-MM-DD_HH-MM-SS_summary.json`
- `outputs/YYYY-MM-DD_HH-MM-SS_summary.md`

## Architecture

The application uses a multi-agent architecture:
- **Scraper Agent**: Fetches and parses Hacker News articles and comments
- **Filter Agent**: Identifies AI-related topics
- **Summarizer Agent**: Generates summaries using DeepSeek API

## Configuration

Edit `.env` to customize your setup:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | - | Your DeepSeek API key (required) |
| `DEEPSEEK_MODEL` | `deepseek-chat` | DeepSeek model to use |
| `TELEGRAM_BOT_TOKEN` | - | Telegram bot token from @BotFather |

## License

MIT
