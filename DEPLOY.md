# Production Deployment Guide

Two deployment options — pick whichever fits your setup.

---

## Option A: Docker (Recommended)

Best for: VPS servers, Oracle Cloud, any machine with Docker installed.
Everything runs in containers — no dependency conflicts, easy to restart.

### 1. Get a server

| Platform | Cost | Specs |
|---|---|---|
| **Oracle Cloud Free Tier** | Free forever | 4 CPU, 24GB RAM |
| **DigitalOcean Droplet** | $6/month | 1 CPU, 1GB RAM |
| **Hetzner Cloud CX11** | ~€4/month | 2 CPU, 2GB RAM |
| **Contabo VPS** | ~$5/month | 4 CPU, 8GB RAM |

Oracle Cloud Free Tier is the best deal — genuinely free, enough RAM to run this bot reliably.

### 2. Install Docker on your server

```bash
# SSH into your server
ssh root@YOUR_SERVER_IP

# Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker
```

### 3. Upload your project

```bash
# From your local machine:
scp -r bball-buffer-bot/ root@YOUR_SERVER_IP:/opt/bball-buffer-bot/

# Or clone from GitHub (after pushing your code):
ssh root@YOUR_SERVER_IP
git clone https://github.com/YOUR_USERNAME/bball-buffer-bot.git /opt/bball-buffer-bot
```

### 4. Set up environment variables

```bash
cd /opt/bball-buffer-bot
cp .env.example .env
nano .env
```

Fill in:
```
BUFFER_API_KEY=your_actual_buffer_api_key
BUFFER_CHANNEL_ID=your_actual_channel_id
AI_PROVIDER=groq
AI_MODEL=mistral
```

### 5. Deploy

```bash
chmod +x deploy.sh
./deploy.sh docker
```

This will:
- Build the bot container
- Use Groq as the AI provider
- Pull the Mistral AI model
- Start the bot
- Auto-restart on crash

### 6. Verify it's running

```bash
./deploy.sh status     # check containers
./deploy.sh logs       # tail live logs
```

---

## Option B: Bare Metal / Systemd (No Docker)

Best for: if you prefer direct server setup without Docker.

### 1. SSH into your server and upload files

```bash
scp -r bball-buffer-bot/ root@YOUR_SERVER_IP:/opt/bball-buffer-bot/
ssh root@YOUR_SERVER_IP
cd /opt/bball-buffer-bot
cp .env.example .env
nano .env   # fill in your keys
```

### 2. Deploy

```bash
chmod +x deploy.sh
sudo ./deploy.sh server
```

This automatically installs Python, creates a `botuser` system account,
sets up a virtualenv, and installs a systemd service that auto-starts on boot.

### 3. Common commands

```bash
sudo systemctl status bball-bot       # check status
sudo systemctl restart bball-bot      # restart
sudo systemctl stop bball-bot         # stop
journalctl -u bball-bot -f            # live logs
```

---

## Pushing Updates

After changing any code:

```bash
./deploy.sh update
```

This pulls the latest code and restarts the bot automatically.

---

## Health Monitoring

Run the health check manually:

```bash
python healthcheck.py
```

To run it automatically every 5 minutes via cron:

```bash
crontab -e
```
Add this line:
```
*/5 * * * * cd /opt/bball-buffer-bot && python healthcheck.py --json >> logs/health.log 2>&1
```

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `BUFFER_API_KEY` | ✅ Yes | Your Buffer API key |
| `BUFFER_CHANNEL_ID` | ✅ Yes | Your X/Twitter channel ID in Buffer |
| `AI_PROVIDER` | No | `groq` (default) |
| `AI_MODEL` | No | `llama3-70b-8192` (default) |
| `GROQ_API_KEY` | ✅ Yes | Free key from console.groq.com |
| `LOG_LEVEL` | No | `INFO` (default), `DEBUG`, `WARNING` |

---

## Oracle Cloud Free Tier Setup (Step by Step)

Oracle gives you a permanently free VM — enough to run this bot 24/7 at zero cost.

1. Sign up at https://cloud.oracle.com (requires credit card, never charged on free tier)
2. Create a **Compute Instance**:
   - Shape: `VM.Standard.A1.Flex` (4 OCPU, 24GB RAM — free)
   - OS: Ubuntu 22.04
3. Download the SSH key when prompted
4. Once the instance is running, SSH in:
   ```bash
   ssh -i ~/your-key.pem ubuntu@YOUR_INSTANCE_IP
   ```
5. Follow Option A (Docker) from step 2 above

---

## Troubleshooting Production

| Problem | Fix |
|---|---|
| Bot stops after a few hours | Check logs: `./deploy.sh logs` |
| Out of memory | Use Groq instead — set `AI_PROVIDER=groq` in `.env` |
| Buffer API 401 error | Regenerate API key at buffer.com/settings/api |
| Container won't start | Check `.env` has no extra spaces around `=` |
| Can't connect to server | Open port 22 in your cloud provider's firewall |
