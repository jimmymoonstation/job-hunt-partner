"""
Proactive notifications pushed to the #job-hunt Discord channel.
Called by the scheduler.
"""
import logging
import os

import httpx

logger = logging.getLogger(__name__)

API_BASE = "http://127.0.0.1:5057/api"
DISCORD_API = "https://discord.com/api/v10"
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
JOB_HUNT_CHANNEL_ID = os.getenv("JOB_HUNT_CHANNEL_ID", "")


async def send_morning_summary():
    if not JOB_HUNT_CHANNEL_ID:
        return
    try:
        async with httpx.AsyncClient() as client:
            stats = (await client.get(f"{API_BASE}/stats?period=week")).json()
            new_jobs = (await client.get(f"{API_BASE}/jobs?status=new&limit=5")).json()

        applied = stats["applications"].get("applied", 0)
        interviews = stats.get("interviews_scheduled", 0)
        days_left = stats.get("days_remaining", 60)
        new_count = new_jobs.get("total", 0)

        msg = (
            f"Good morning! **Day {stats.get('days_since_start', 1)}** of your job search. "
            f"**{days_left} days remaining.**\n\n"
            f"This week: **{applied} applications**, **{interviews} interview(s)**\n"
            f"New openings since yesterday: **{new_count}**\n"
        )
        if applied < 3:
            msg += "\nYou're behind on applications. Open the dashboard and knock out 2-3 today."

        await _send(msg)
    except Exception as e:
        logger.error(f"Morning summary failed: {e}")


async def send_evening_checkin():
    if not JOB_HUNT_CHANNEL_ID:
        return
    try:
        async with httpx.AsyncClient() as client:
            stats = (await client.get(f"{API_BASE}/stats?period=today")).json()

        today_apps = stats["applications_total"]
        if today_apps >= 2:
            return  # doing fine, no need to check in

        msg = (
            f"Hey — only **{today_apps}** application(s) today. "
            "How's it going? Anything blocking you, or just a slow day?\n"
            "Tell me what you worked on and I'll help you plan tomorrow."
        )
        await _send(msg)
    except Exception as e:
        logger.error(f"Evening check-in failed: {e}")


async def notify_new_jobs(jobs: list[dict]):
    if not JOB_HUNT_CHANNEL_ID or not jobs:
        return
    try:
        lines = [f"**{len(jobs)} new opening(s) found:**"]
        for j in jobs[:5]:
            lines.append(f"• **{j['job_title']}** @ {j['company_name']} — {j.get('location', 'Unknown')} → {j['url']}")
        if len(jobs) > 5:
            lines.append(f"  _(+{len(jobs) - 5} more in dashboard)_")
        await _send("\n".join(lines))
    except Exception as e:
        logger.error(f"New jobs notification failed: {e}")


async def _send(content: str):
    if not BOT_TOKEN or not JOB_HUNT_CHANNEL_ID:
        logger.warning("Discord not configured — skipping notification")
        return
    chunks = [content[i:i+1900] for i in range(0, len(content), 1900)]
    async with httpx.AsyncClient() as client:
        for chunk in chunks:
            await client.post(
                f"{DISCORD_API}/channels/{JOB_HUNT_CHANNEL_ID}/messages",
                headers={"Authorization": f"Bot {BOT_TOKEN}"},
                json={"content": chunk},
            )
