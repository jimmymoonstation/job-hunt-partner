#!/usr/bin/env python3
"""
Create the #job-hunt Discord channel and update .env with the channel ID.
Run once during setup.
"""
import os, sys, json, urllib.request, urllib.parse

TOKEN = None
SERVICE_FILE = "/etc/systemd/system/claude-discord-bot.service"
ENV_FILE = "/opt/job-hunt-partner/.env"
GUILD_ID = "1494232293324230789"

# Read token from service file
with open(SERVICE_FILE) as f:
    for line in f:
        if "DISCORD_BOT_TOKEN=" in line or "TOKEN=" in line:
            TOKEN = line.strip().split("=", 1)[1].strip().strip('"')
            break

if not TOKEN:
    print("Could not find Discord bot token in service file")
    sys.exit(1)

headers = {
    "Authorization": f"Bot {TOKEN}",
    "Content-Type": "application/json",
}

# Check if #job-hunt already exists
req = urllib.request.Request(
    f"https://discord.com/api/v10/guilds/{GUILD_ID}/channels",
    headers=headers,
)
channels = json.loads(urllib.request.urlopen(req).read())
existing = next((c for c in channels if c["name"] == "job-hunt"), None)

if existing:
    channel_id = existing["id"]
    print(f"Channel #job-hunt already exists: {channel_id}")
else:
    data = json.dumps({
        "name": "job-hunt",
        "type": 0,
        "topic": "Job hunting partner — new openings, applications tracker, interview prep",
        "position": 99,
    }).encode()
    req = urllib.request.Request(
        f"https://discord.com/api/v10/guilds/{GUILD_ID}/channels",
        data=data,
        headers=headers,
        method="POST",
    )
    channel = json.loads(urllib.request.urlopen(req).read())
    channel_id = channel["id"]
    print(f"Created #job-hunt channel: {channel_id}")

# Update .env
with open(ENV_FILE, "r") as f:
    content = f.read()

if "JOB_HUNT_CHANNEL_ID=" in content:
    lines = content.splitlines()
    lines = [f"JOB_HUNT_CHANNEL_ID={channel_id}" if l.startswith("JOB_HUNT_CHANNEL_ID=") else l for l in lines]
    content = "\n".join(lines) + "\n"
else:
    content += f"\nJOB_HUNT_CHANNEL_ID={channel_id}\n"

with open(ENV_FILE, "w") as f:
    f.write(content)

# Also write token to .env if not there
if "DISCORD_BOT_TOKEN=" not in content:
    with open(ENV_FILE, "a") as f:
        f.write(f"DISCORD_BOT_TOKEN={TOKEN}\n")

print(f"Updated .env with JOB_HUNT_CHANNEL_ID={channel_id}")
print("Done! Restart the job-hunter service: systemctl restart job-hunter")
