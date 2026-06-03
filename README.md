# World Cup 2026 News Bot — Buffer API Edition

A lightweight FIFA World Cup 2026 news listener that polls configured RSS feeds, generates tweet content from new articles, and records post activity in SQLite.

> Note: This bot is **strictly focused on FIFA World Cup 2026** content only. All feeds, AI prompts, and post generation are tailored exclusively to WC2026 news, teams, venues, matches, and players.

## What this project contains

- `main.py` — bot orchestration, config loading, logging, article processing loop
- `config.yaml` — feed list (World Cup 2026 sources only), Buffer settings, AI settings, listener options, logging settings
- `buffer_client.py` — Buffer API posting client
- `fetcher.py` — RSS feed fetcher (Google News RSS for World Cup 2026 keywords)
- `generator.py` — AI-powered tweet post generator (World Cup 2026 persona)
- `database.py` — SQLite persistence for seen articles and posting status
- `healthcheck.py` — local health check script for monitoring
- `deploy.sh` — Docker / server deployment helper
- `docker-compose.yml` — Docker Compose deployment definition
- `worldcup-bot.service` — systemd service unit for bare-metal installs
- `requirements.txt` — Python dependencies

## Key behaviors

- Loads settings from `config.yaml` and environment variables in `.env`
- Tracks seen articles and posting state in `data/bot.db`
- Writes logs to `logs/bot.log`
- Polls RSS feeds every `listener.poll_interval_seconds`
- Generates World Cup 2026-themed original tweets using `generator.py` (Groq/LLaMA)
- Posts to Buffer using `buffer_client.py`

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
AI_MODEL=llama-3.3-70b-versatile
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

4. Review `config.yaml` — all feeds are pre-configured for World Cup 2026 news sources.

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
| `AI_MODEL` | No | `llama-3.3-70b-versatile` (default) |
| `GROQ_API_KEY` | Yes | Groq API key |
| `LOG_LEVEL` | No | `INFO`, `DEBUG`, `WARNING` |

### Important note about `BUFFER_CHANNEL_ID`

This is the Buffer profile/channel ID for the X/Twitter account you want the bot to post to. It is not your Twitter handle.

If you want to discover it from Buffer, use the Buffer developer tools or inspect the profile list response in Buffer's web UI or API.

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

This installs dependencies, creates a `botuser` system account,
sets up a virtualenv, and installs a systemd service at `/etc/systemd/system/worldcup-bot.service`.

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
4. It polls World Cup 2026 RSS feeds periodically
5. For each new article it:
   - generates a World Cup 2026-themed original tweet
   - saves a pending post record
   - posts to Buffer via Buffer API
   - updates database status