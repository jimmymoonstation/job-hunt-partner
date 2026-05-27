# Discord Bot Design

The Discord bot is your active job hunting partner. It lives in the `#job-hunt` channel in the Moon Station server and does two things:

1. **Proactive alerts** — pushes notifications when something happens (new jobs, interview reminders)
2. **Conversational partner** — talks to you, tracks your mood, helps you prep

## Channel

- **Server:** Moon Station (guild ID: `1494232293324230789`)
- **Channel:** `#job-hunt` (created during setup)

The bot uses the existing `claude-discord-bot` infrastructure but adds a job-hunt-specific module loaded when the target channel is `#job-hunt`.

## Conversation Design

The bot is not a command-based bot. It's a conversation partner. You talk to it naturally.

### Context the bot always has available

Before generating any response, the bot fetches fresh stats from the API:
```
- Days remaining until visa deadline
- Applications this week / today
- Upcoming interviews
- New job openings since last check
- Last conversation timestamp
```

This context is injected into the Claude system prompt so every response is grounded in reality.

### System Prompt (injected per message)

```
You are a supportive but direct job hunting partner. Your user is on a visa 
deadline — they have {days_remaining} days to land a job. No sugarcoating.

Current status:
- Applications this week: {apps_this_week}
- Applications today: {apps_today}  
- Active interviews: {active_interviews}
- Upcoming interview: {next_interview} (in {days_until} days)
- New job openings since last check: {new_jobs_count}

Today is {date}. The user's goal is 3+ applications per day.

Be encouraging, specific, and action-oriented. If they're behind on applications,
say so clearly. If they have an interview coming up, prioritize prep. 
Keep responses concise — under 200 words unless they ask for detail.
```

### Conversation History

The last 20 messages are stored in `discord_sessions` and included in every Claude call. This gives the bot memory within a session and across days.

## Proactive Notifications (pushed by API)

The bot receives webhooks from the API and posts to `#job-hunt` without being asked.

### New Jobs Alert
```
🆕 5 new openings match your search:
• Senior SWE @ Stripe (SF) — posted 2h ago → [link]
• Backend Engineer @ Notion (Remote) — posted 4h ago → [link]
• Software Engineer L5 @ Google (MTV) — posted 6h ago → [link]
  + 2 more → [dashboard link]
```

### Interview Reminder (24h before)
```
📅 Interview tomorrow: Technical round @ Stripe
Time: Jan 20 at 2:00 PM PST

Want to do a quick prep session? Just say "prep" and I'll walk you 
through likely questions for a Stripe technical interview.
```

### Daily Morning Summary (9:00 AM)
```
Good morning! Day 15 of your job search. 46 days remaining.

This week: 8 applications, 1 phone screen
Today's new openings: 12 (3 match well)

You're slightly behind target (3/day). Got 20 minutes? 
Open the dashboard and knock out 2-3 quick applications.
```

### Evening Check-in (6:00 PM, only if < 2 applications today)
```
Hey — only 1 application today. How's it going? 
Is something blocking you, or just a slow day?
```

## Conversation Triggers (user-initiated)

These are natural language — the bot detects intent:

| User says | Bot does |
|---|---|
| "prep" / "interview prep" | Fetches next interview, generates tailored prep guide |
| "how am I doing" | Detailed stats + honest assessment |
| "show me new jobs" | Lists latest 5 openings with links |
| "I applied to X" | Prompts to log it in the tracker (or does it via API) |
| "I got an interview at X" | Congratulates + asks for details + schedules reminder |
| "I got rejected from X" | Empathy + "want me to find similar roles?" |
| "I'm feeling burnt out" | Supportive response + suggests taking a break |
| "help me write a cover letter for X" | Pulls job description + resume, drafts cover letter |

## Module Structure

```python
# src/discord/job_hunt_module.py

class JobHuntModule:
    def should_handle(self, channel_name: str) -> bool:
        return channel_name == "job-hunt"
    
    async def handle_message(self, message: discord.Message) -> str:
        stats = await self.api.get_stats()
        history = await self.db.get_session(message.channel.id)
        
        system_prompt = self.build_system_prompt(stats)
        response = await self.claude.message(
            system=system_prompt,
            messages=history + [{"role": "user", "content": message.content}]
        )
        
        await self.db.update_session(message.channel.id, message, response)
        return response
    
    async def send_notification(self, notif_type: str, payload: dict):
        channel = self.get_job_hunt_channel()
        message = self.format_notification(notif_type, payload)
        await channel.send(message)
```

## Configuration

The bot token is already in `/etc/systemd/system/claude-discord-bot.service`.
The Claude API key is read from the same environment.
The job-hunt module is activated by setting `JOB_HUNT_CHANNEL_ID` in the service env.
