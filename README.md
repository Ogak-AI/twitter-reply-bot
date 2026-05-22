# Basketball News Bot — Buffer API Edition

A lightweight basketball news listener that polls configured RSS feeds, generates tweet content from new articles, and records post activity in SQLite.

> Note: In the current repository state, the RSS fetcher and Buffer posting components are stubbed. This README documents the structure and how to complete the bot for production use.

## What this project contains

- `main.py` — bot orchestration, config loading, logging, article processing loop
- `config.yaml` — feed list, Buffer settings, AI settings, listener options, logging settings
- `buffer_client.py` — Buffer posting stub
- `fetcher.py` — RSS fetcher stub
- `generator.py` — simple tweet generator stub
- `database.py` — SQLite persistence for seen articles and posting status
- `healthcheck.py` — local health check script for monitoring
- `deploy.sh` — Docker / server deployment helper
- `docker-compose.yml` — Docker Compose deployment definition
- `bball-bot.service` — systemd service unit for bare-metal installs
- `requirements.txt` — Python dependencies

## Key behaviors

- Loads settings from `config.yaml` and environment variables in `.env`
- Tracks seen articles and posting state in `data/bot.db`
- Writes logs to `logs/bot.log`
- Polls RSS feeds every `listener.poll_interval_seconds`
- Generates tweet copy from article data using `generator.py`
- Posts to Buffer using `buffer_client.py` (currently a stub)

## Requirements

- Python 3.11+ / 3.14
- `pip`
- `virtualenv` support (built into Python 3)
- `docker` and `docker-compose` for container deployment

## Setup

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Edit `.env` and fill in your values:

```dotenv
BUFFER_API_KEY=your_actual_buffer_api_key
BUFFER_CHANNEL_ID=your_actual_channel_id
AI_PROVIDER=groq
AI_MODEL=llama3-70b-8192
GROQ_API_KEY=your_groq_api_key_here
LOG_LEVEL=INFO
```

3. Create a Python virtual environment and install dependencies:

```bash
python -m venv venv
# macOS / Linux
source venv/bin/activate
# Windows PowerShell
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

4. Review `config.yaml` and adjust feed sources, AI model settings, or Buffer mode.

## Running locally

```bash
python main.py
```


## Health check

Manual run:

```bash
python healthcheck.py
```

JSON output (for monitoring tools):

```bash
python healthcheck.py --json
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `BUFFER_API_KEY` | Yes | Buffer API access token |
| `BUFFER_CHANNEL_ID` | Yes | Buffer X/Twitter channel/profile ID |
| `AI_PROVIDER` | No | `groq` (default) |
| `AI_MODEL` | No | `llama3-70b-8192` (default) |
| `GROQ_API_KEY` | Yes | Groq API key |
| `LOG_LEVEL` | No | `INFO`, `DEBUG`, `WARNING` |

### Important note about `BUFFER_CHANNEL_ID`

This is the Buffer profile/channel ID for the X/Twitter account you want the bot to post to. It is not your Twitter handle.

If you want to discover it from Buffer, use the Buffer developer tools or inspect the profile list response in Buffer’s web UI or API.

## Current implementation notes

This repo contains placeholder logic in a few key places:

- `fetcher.py` — returns no articles by default. Replace `fetch_new_articles()` with actual RSS parsing logic.
- `generator.py` — returns a simple title-based tweet. Replace `generate_tweet()` with a richer AI/text generation workflow.
- `buffer_client.py` — returns a stubbed failure response. Implement actual Buffer API calls here.

## Recommended extension points

- Add RSS parsing in `fetcher.py` using `feedparser` or another RSS library
- Improve generation in `generator.py` with an AI provider or template system
- Implement Buffer posting in `buffer_client.py` using `https://api.buffer.com` or the current Buffer GraphQL API
- Add error handling, retries, and rate limiting for Buffer and RSS fetches

## Deployment

### Docker

```bash
chmod +x deploy.sh
./deploy.sh docker
```

The Docker Compose setup:

- mounts `./data` for the SQLite database
- mounts `./logs` for log persistence
- reads environment variables from `.env`

### Server / systemd

```bash
chmod +x deploy.sh
sudo ./deploy.sh server
```

This installs dependencies, creates a virtualenv, and installs a systemd service at `/etc/systemd/system/bball-bot.service`.

### Common deployment commands

```bash
./deploy.sh update
./deploy.sh status
./deploy.sh logs
./deploy.sh stop
```

## Logs and database

- Logs: `logs/bot.log`
- Database: `data/bot.db`

## How the bot works

1. `main.py` loads the YAML config and expands env variables
2. It initializes logging and the SQLite database
3. It scans for already seen posts
4. It polls RSS feeds periodically
5. For each new article it:
   - generates tweet content
   - saves a pending post record
   - posts to Buffer via Buffer GraphQL API
   - updates database status

## Notes

Because the current code uses stub implementations, the bot will not post to Buffer or fetch real RSS content until those stubs are completed.

If you want, I can also add:

- a working RSS fetcher implementation
- a real Buffer API client in `buffer_client.py`
- a stronger tweet generation pipeline using your AI provider
