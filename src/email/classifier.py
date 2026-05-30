"""
Rule-based email classifier for job hunt emails.
Returns category + extracted company/job_title.
"""
import re

# Ordered rules — first match wins.
# application_confirm must come before interview: many confirmation emails
# contain phrases like "next steps" or "we'll be in touch" that are too vague
# to reliably signal an actual interview invitation.
_RULES = [
    ("offer", [
        "pleased to offer", "offer of employment", "we'd like to offer you",
        "formal offer", "compensation package", "offer letter",
    ]),
    ("application_confirm", [
        "thank you for applying", "we received your application",
        "we've received your", "application has been received", "application received",
        "you've applied", "you have applied", "we got your application",
        "successfully submitted", "application submitted",
        "your application for", "thanks for applying",
        "we'll be in touch", "keep you posted", "review your application",
        "reviewing applications", "be in touch soon",
    ]),
    ("assessment", [
        "coding challenge", "take-home", "take home assignment",
        "hackerrank", "codesignal", "codility", "karat",
        "technical assessment", "technical screen", "skills assessment",
        "complete the following", "online assessment",
    ]),
    ("rejection", [
        "decided to move forward with other candidates",
        "not moving forward", "will not be moving forward",
        "unfortunately", "regret to inform", "we won't be",
        "position has been filled", "decided not to",
        "we have decided", "not selected", "other candidates",
        "not a match", "no longer considering",
    ]),
    ("interview", [
        "schedule an interview", "invite you to interview", "we'd like to interview",
        "like to speak with you", "set up a call", "would love to connect",
        "please select a time", "book a time", "calendly.com", "savvycal",
        "zoom interview", "phone screen", "video interview",
        "meet with our team", "moving forward with your application",
        "excited to move you forward", "advance to the next round",
        "invite you to schedule", "book your interview",
    ]),
]

# Senders that are clearly job-related even if body is sparse
_JOB_SENDER_DOMAINS = {
    "greenhouse.io", "lever.co", "ashbyhq.com", "myworkday.com",
    "smartrecruiters.com", "jobvite.com", "icims.com", "taleo.net",
    "successfactors.com", "workable.com", "breezy.hr",
    "linkedin.com", "indeed.com", "glassdoor.com",
}

# LinkedIn notification email senders
_LINKEDIN_MESSAGE_SENDERS = {
    "messages-noreply@linkedin.com",
    "inmail-hit-reply@linkedin.com",
}

_LINKEDIN_MESSAGE_SUBJECTS = [
    "sent you a message",
    "you have a new message",
    "new message from",
    "replied to your message",
    "sent you an inmail",
    "you have a new inmail",
    "new inmail from",
]


def classify(subject: str, body: str, from_address: str) -> str:
    """Return one of: offer, interview, assessment, rejection, application_confirm, linkedin_message, other."""
    addr = from_address.lower()

    # LinkedIn direct messages — detect before general rules
    if addr in _LINKEDIN_MESSAGE_SENDERS or "linkedin.com" in addr:
        subj_lower = subject.lower()
        if any(p in subj_lower for p in _LINKEDIN_MESSAGE_SUBJECTS):
            return "linkedin_message"

    text = (subject + " " + body).lower()
    for category, phrases in _RULES:
        if any(p in text for p in phrases):
            return category
    return "other"


def extract_linkedin_sender(subject: str) -> str | None:
    """Extract the sender's name from a LinkedIn message notification subject."""
    # "[Name] sent you a message" / "New message from [Name]" / "[Name] replied to your message"
    patterns = [
        r'^(.+?)\s+sent you a(?:n inmail)? message',
        r'^(.+?)\s+replied to your message',
        r'new (?:inmail|message) from\s+(.+?)(?:\s+on linkedin)?$',
        r'you have a new message from\s+(.+?)(?:\s+on linkedin)?$',
    ]
    for pat in patterns:
        m = re.search(pat, subject.strip(), re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def extract_linkedin_preview(body: str) -> str:
    """Extract the message text preview from a LinkedIn notification email body."""
    # LinkedIn bodies look like:
    #   "Hi [you],\n\n[Sender] sent you a message on LinkedIn.\n\n[preview text]\n\nView message\n\n..."
    # Try to grab text between the intro line and the "View message" / footer CTA
    body = re.sub(r'\r\n', '\n', body)

    # Strip everything after common footer markers
    for marker in ["View message", "Open LinkedIn", "Unsubscribe", "This email was intended for"]:
        idx = body.find(marker)
        if idx != -1:
            body = body[:idx]

    # Drop the greeting / intro sentence (first paragraph)
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', body.strip()) if p.strip()]
    # Skip short intro lines like "Hi Jimmy," or "[Name] sent you a message on LinkedIn."
    for i, para in enumerate(paragraphs):
        if len(para) > 80 or (i > 0 and not re.search(r'sent you|new message|linkedin', para, re.IGNORECASE)):
            return para[:300]

    return paragraphs[-1][:300] if paragraphs else ""


def extract_company(subject: str, body: str, from_address: str,
                    known_companies: list[str]) -> str | None:
    """Try to extract company name from email content."""
    text = subject + " " + body[:2000]

    # 1. Match against known tracked companies (longest match first)
    for company in sorted(known_companies, key=len, reverse=True):
        if company.lower() in text.lower():
            return company

    # 2. Sender domain heuristic: recruiting@company.com → "Company"
    domain_match = re.search(r'@([\w-]+)\.(com|io|co|ai|tech)', from_address.lower())
    if domain_match:
        raw = domain_match.group(1)
        # Skip generic job boards
        if raw not in {"gmail", "yahoo", "outlook", "hotmail", "lever",
                       "greenhouse", "ashby", "workday", "smartrecruiters",
                       "linkedin", "indeed", "glassdoor", "jobvite", "icims"}:
            return raw.replace("-", " ").title()

    # 3. Pattern: "at <Company>" or "from <Company>" in subject
    m = re.search(r'\b(?:at|from|with)\s+([A-Z][A-Za-z0-9& ]{2,30}?)(?:\s+(?:for|is|team|recruiting|HR)|[,!]|$)', subject)
    if m:
        return m.group(1).strip()

    return None


def extract_job_title(subject: str, body: str) -> str | None:
    """Try to extract job title from email content."""
    # Pattern: "for the <Title> role/position"
    m = re.search(
        r'(?:for the|applied (?:for|to)(?: the)?|role of|position of|position:)\s+'
        r'([A-Za-z][A-Za-z0-9 ,/\-&]{3,60}?)'
        r'(?:\s+(?:role|position|job|opportunity)|[,.]|$)',
        subject + " " + body[:500],
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    return None
