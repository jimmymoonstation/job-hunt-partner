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
    """Push immediate alert when the scraper finds new jobs."""
    if not JOB_HUNT_CHANNEL_ID or not jobs:
        return
    try:
        lines = [f"🎯 **{len(jobs)} new job(s) found:**"]
        for j in jobs[:8]:
            url  = j.get("original_url") or j.get("url") or ""
            loc  = j.get("location") or ""
            loc_str = f" — {loc}" if loc else ""
            lines.append(f"• **{j['job_title']}** @ **{j['company_name']}**{loc_str}\n  {url}")
        if len(jobs) > 8:
            lines.append(f"_+{len(jobs) - 8} more — check the dashboard_")
        await _send("\n".join(lines))
    except Exception as e:
        logger.error(f"New jobs notification failed: {e}")


async def send_daily_report():
    """9 PM daily digest: jobs found since last night + call to action for tomorrow."""
    if not JOB_HUNT_CHANNEL_ID:
        return
    try:
        from datetime import datetime, timedelta
        since = (datetime.utcnow() - timedelta(hours=24)).isoformat()

        async with httpx.AsyncClient() as client:
            stats_today  = (await client.get(f"{API_BASE}/stats?period=today")).json()
            stats_all    = (await client.get(f"{API_BASE}/stats?period=all_time")).json()
            new_jobs_r   = (await client.get(
                f"{API_BASE}/jobs?status=new&limit=200&since={since}"
            )).json()
            total_new    = (await client.get(f"{API_BASE}/jobs?status=new&limit=1")).json()

        today_apps   = stats_today.get("applications_total", 0)
        all_apps     = stats_all.get("applications_total", 0)
        interviews   = stats_all.get("interviews_scheduled", 0)
        days_left    = stats_all.get("days_remaining", 0)
        new_since    = new_jobs_r.get("total", 0)
        total_open   = total_new.get("total", 0)

        lines = [
            f"📊 **Daily Job Hunt Report — {datetime.utcnow().strftime('%b %d')}**",
            "",
            f"**Today:** {today_apps} application(s) submitted",
            f"**All-time:** {all_apps} applied · {interviews} interview(s) · {days_left} days remaining",
            f"**New listings discovered today:** {new_since}",
            f"**Total open roles waiting:** {total_open}",
        ]

        # Show top new listings from today
        recent = new_jobs_r.get("jobs") or []
        if recent:
            lines.append("")
            lines.append("**Fresh openings found today:**")
            for j in recent[:6]:
                url = j.get("original_url") or j.get("url") or ""
                lines.append(f"• **{j['job_title']}** @ {j['company_name']} → {url}")
            if new_since > 6:
                lines.append(f"_+{new_since - 6} more in the dashboard_")

        # Call to action
        lines.append("")
        if today_apps == 0:
            lines.append("⚠️ **No applications today.** Open the dashboard and fire off a few — even 2 keeps momentum.")
        elif today_apps < 5:
            lines.append(f"Nice work on {today_apps} today. Aim for 5+ tomorrow to stay on pace.")
        else:
            lines.append(f"🔥 Strong day — {today_apps} applications! Keep it up tomorrow.")

        await _send("\n".join(lines))
    except Exception as e:
        logger.error(f"Daily report failed: {e}")


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
