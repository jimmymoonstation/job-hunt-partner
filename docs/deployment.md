# Deployment Guide

## Server Layout

```
/opt/job-hunt-partner/
├── jobs.db                    ← SQLite database
├── resumes/                   ← uploaded resume files
├── .env                       ← secrets (not in git)
├── src/
│   ├── api/main.py            ← FastAPI app entry point
│   ├── scraper/               ← scraper modules
│   ├── dashboard/             ← static web files
│   └── discord/               ← Discord bot module
├── scripts/
│   ├── init_db.py             ← creates tables
│   └── deploy.sh              ← full deploy script
└── requirements.txt
```

## Ports

| Service | Port | Notes |
|---|---|---|
| trip-admin | 5055 | existing |
| job-hunter API | 5057 | new |

## Nginx Config

`/etc/nginx/sites-available/job-hunter`:

```nginx
# Static dashboard
location /jobs {
    alias /opt/job-hunt-partner/src/dashboard;
    try_files $uri $uri/ /jobs/index.html;
}

# API proxy
location /api/ {
    proxy_pass http://127.0.0.1:5057/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

## Systemd Service

`/etc/systemd/system/job-hunter.service`:

```ini
[Unit]
Description=Job Hunt Partner API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/job-hunt-partner
EnvironmentFile=/opt/job-hunt-partner/.env
ExecStart=/usr/bin/python3 -m uvicorn src.api.main:app --host 127.0.0.1 --port 5057
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Environment Variables

`.env` (copy from `.env.example`):

```bash
BRAVE_API_KEY=your_brave_search_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key     # for Discord bot coaching
DATABASE_URL=sqlite:////opt/job-hunt-partner/jobs.db
JOB_HUNT_CHANNEL_ID=                         # filled after Discord channel created
```

## Deploy Steps

```bash
# 1. Install dependencies
cd /opt/job-hunt-partner
pip3 install -r requirements.txt

# 2. Set up environment
cp .env.example .env
# edit .env with real keys

# 3. Initialize database
python3 scripts/init_db.py

# 4. Set up nginx
cp nginx/job-hunter.conf /etc/nginx/sites-available/job-hunter
ln -s /etc/nginx/sites-available/job-hunter /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# 5. Start API service
cp systemd/job-hunter.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable job-hunter
systemctl start job-hunter

# 6. Create Discord channel + extend bot
python3 scripts/setup_discord.py
systemctl restart claude-discord-bot
```

## Brave Search API Setup

1. Go to https://brave.com/search/api/
2. Sign up for free account
3. Create an API key (free tier: 2,000 req/month)
4. Add to `.env` as `BRAVE_API_KEY`

## Monitoring

```bash
systemctl status job-hunter
journalctl -u job-hunter -f
journalctl -u claude-discord-bot -f
```
