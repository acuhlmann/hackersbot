# AGENTS.md - AI Agent Navigation Guide

This file helps AI coding agents (Claude, Copilot, Cursor, etc.) navigate and understand this project quickly.

## Project Overview

**HackersBot** is a multi-agent Python app that scrapes Hacker News, classifies articles as AI-related using DeepSeek LLM, and generates summaries. Three interfaces: CLI, web UI, Telegram bot.

## Key Entry Points

| What | File | Notes |
|------|------|-------|
| CLI | `src/main.py` | Click-based CLI, orchestrates the agent pipeline |
| Web server | `serve.py` | HTTP server + REST API + SSE streaming |
| Telegram bot | `src/telegram_bot.py` | python-telegram-bot async handlers |
| Web UI | `web/index.html` | Vanilla JS SPA, no build step |
| Docker | `Dockerfile`, `docker-compose.yml` | Multi-stage build, non-root user |
| CI/CD | `.github/workflows/python-app.yml` (test), `.github/workflows/deploy.yml` (deploy) | GCP Compute Engine target |

## Agent Pipeline (core logic)

All three interfaces use the same pipeline:

```
ScraperAgent → FilterAgent → SummarizerAgent
```

| Agent | File | Responsibility |
|-------|------|---------------|
| `ScraperAgent` | `src/agents/scraper_agent.py` | Scrapes HN articles + comments via BeautifulSoup |
| `FilterAgent` | `src/agents/filter_agent.py` | Classifies articles as AI-related via LLM |
| `SummarizerAgent` | `src/agents/summarizer_agent.py` | Generates article summaries, comment sentiment, topic extraction |

## LLM Layer

| File | Role |
|------|------|
| `src/models/llm_client.py` | Unified LLM interface with event instrumentation |
| `src/models/deepseek_client.py` | DeepSeek API wrapper using OpenAI SDK |

- Uses `openai` SDK pointed at `https://api.deepseek.com`
- Model: `deepseek-chat` (configurable via `DEEPSEEK_MODEL` env var)
- API key: `DEEPSEEK_API_KEY` env var (required)

## Utilities

| File | Role |
|------|------|
| `src/utils/storage.py` | Save JSON/Markdown summaries to disk |
| `src/utils/formatters.py` | Format output for console, markdown, JSON |
| `web/generate_index.py` | Generate `summaries/index.json` and `summaries/adhoc/index.json` |

## Web Server Details (`serve.py`)

- Built on Python's `http.server` (no framework)
- Multi-threaded request handling
- SSE endpoint (`/refresh-stream`) for real-time progress
- Rate limiting: 1 refresh/hour, 10 ad-hoc/day per article
- Scheduled daily refresh at 6:00 AM GMT+8
- API prefix: `/api/` (status, refresh, adhoc-summaries)
- Serves `web/index.html` and `summaries/` directory

## Data Storage

| Directory | Contents |
|-----------|----------|
| `summaries/` | Daily summary JSON files (one per day, overwritten) |
| `summaries/adhoc/` | Single-article on-demand summaries |
| `outputs/` | CLI output (JSON + Markdown with timestamps) |

Filename patterns:
- Daily: `YYYY-MM-DD_summary.json`
- CLI: `YYYY-MM-DD_HH-MM-SS_summary.json` and `.md`

## Testing

| File | Tests |
|------|-------|
| `tests/conftest.py` | Shared fixtures: sample articles, mock LLM client, sample HTML |
| `tests/test_scraper_agent.py` | Scraping and comment parsing |
| `tests/test_filter_agent.py` | AI classification |
| `tests/test_summarizer_agent.py` | Summarization logic |
| `tests/test_serve.py` | Web server endpoints and rate limiting |
| `tests/test_formatters.py` | Output formatting |
| `tests/test_storage.py` | File persistence |
| `tests/test_generate_index.py` | Index generation |

Run: `pytest -v`

## Deployment

- **Target:** GCP Compute Engine `hn-vm` in `us-central1-a` (Always Free e2-micro), project `photogroup-215600`
- **Public URL:** `https://hackernews.photogroup.network` → nginx (:443) → Docker `127.0.0.1:18080`
- **Script:** `deploy-docker.sh` (builds Docker image on VM, runs via docker-compose)
- **TLS:** `setup-ssl.sh` / certbot on the VM (Cloudflare A record must stay DNS-only / grey cloud)
- **VM scripts:** `scripts/vm-startup.sh` (boot cleanup), `scripts/vm-disk-cleanup.sh`
- **CI trigger:** Push to `main` → tests pass → auto-deploy
- **Secrets needed:** `GCP_SA_KEY`, `DEEPSEEK_API_KEY` in GitHub repo secrets

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DEEPSEEK_API_KEY` | Yes | DeepSeek API authentication |
| `DEEPSEEK_MODEL` | No | Model name (default: `deepseek-chat`) |
| `TELEGRAM_BOT_TOKEN` | For bot | Telegram bot token |
| `PORT` | No | Web server port (default: `8000`) |
| `BIND_ADDRESS` | No | Server bind address (default: `0.0.0.0`) |

## Common Tasks

**Add a new LLM provider:** Implement a new client in `src/models/`, wire it into `llm_client.py`.

**Add a new output interface:** Use the same agent pipeline (`ScraperAgent → FilterAgent → SummarizerAgent`). See `src/main.py` for the simplest example.

**Add a new API endpoint:** Add a handler method in `serve.py`, route it in `do_GET()` or `do_POST()`.

**Modify scraping behavior:** Edit `src/agents/scraper_agent.py`. Note the 1-second delay between requests to be respectful.

**Change summary format:** Edit `src/utils/formatters.py` for output formatting, or `src/agents/summarizer_agent.py` for LLM prompt changes.
