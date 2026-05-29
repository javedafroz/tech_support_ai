"""Ten diverse support scenarios for live OpenAI + Zammad integration tests."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    name: str
    role: str
    department: str


@dataclass(frozen=True)
class LiveTicketScenario:
    id: str
    category: str
    user_goal: str
    initial_complaint_hint: str
    fact_sheet: dict[str, str]
    title_keywords: tuple[str, ...]
    persona: Persona


_DEFAULT_PERSONA = Persona(name="Alex Morgan", role="Analyst", department="Operations")


LIVE_TICKET_SCENARIOS: tuple[LiveTicketScenario, ...] = (
    LiveTicketScenario(
        id="vpn_network",
        category="network",
        user_goal="Get VPN working from home so I can access internal tools again.",
        initial_complaint_hint="VPN keeps disconnecting when working remotely.",
        fact_sheet={
            "device": "MacBook, macOS 14",
            "software": "Cisco AnyConnect",
            "error": "DPD timeout after about 30 seconds",
            "when_started": "Yesterday afternoon",
            "impact": "Cannot reach Jira or internal tools — completely blocked from work",
            "urgency": "High",
        },
        title_keywords=("vpn", "anyconnect", "network", "disconnect", "dpd", "timeout", "cisco", "internal"),
        persona=_DEFAULT_PERSONA,
    ),
    LiveTicketScenario(
        id="email_outlook",
        category="email",
        user_goal="Fix Outlook so new emails sync to my laptop again.",
        initial_complaint_hint="Outlook stopped syncing inbox since this morning.",
        fact_sheet={
            "software": "Microsoft Outlook 365",
            "symptom": "Shows 'Need Password', no new mail since 8am",
            "when_started": "This morning",
            "workaround": "Webmail works in Chrome",
            "impact": "May miss urgent client emails during meetings today",
            "urgency": "High",
        },
        title_keywords=("outlook", "email", "sync", "mail"),
        persona=Persona(name="Jordan Lee", role="Account Manager", department="Sales"),
    ),
    LiveTicketScenario(
        id="access_locked",
        category="access_management",
        user_goal="Unlock my domain account so I can log in and work.",
        initial_complaint_hint="Locked out after too many password attempts.",
        fact_sheet={
            "symptom": "Login screen says account locked",
            "when_started": "About an hour ago",
            "attempts": "Self-service password reset failed",
            "impact": "Cannot approve payroll tasks due today",
            "urgency": "High",
        },
        title_keywords=("locked", "password", "account", "access", "login"),
        persona=Persona(name="Sam Patel", role="Finance Specialist", department="Finance"),
    ),
    LiveTicketScenario(
        id="hardware_boot",
        category="hardware",
        user_goal="Get my company laptop booting again so I can work.",
        initial_complaint_hint="Laptop stuck on spinning logo after restart.",
        fact_sheet={
            "device": "Dell Latitude 5540, Windows 11",
            "symptom": "Stuck on Windows logo for 20+ minutes",
            "when_started": "After overnight Windows update",
            "impact": "No access to files on device — cannot work",
            "urgency": "High",
        },
        title_keywords=("laptop", "boot", "hardware", "dell", "windows"),
        persona=_DEFAULT_PERSONA,
    ),
    LiveTicketScenario(
        id="software_excel",
        category="software",
        user_goal="Stop Excel from crashing when opening finance spreadsheets.",
        initial_complaint_hint="Excel crashes opening files with macros from Finance share.",
        fact_sheet={
            "software": "Microsoft Excel 365",
            "symptom": "Closes immediately; error mentions add-in problem",
            "when_started": "Started today",
            "workaround": "Safe mode works but macros are required",
            "impact": "Month-end reporting due tomorrow",
            "urgency": "High",
        },
        title_keywords=("excel", "crash", "macro", "software", "office"),
        persona=Persona(name="Riley Chen", role="Financial Analyst", department="Finance"),
    ),
    LiveTicketScenario(
        id="security_phishing",
        category="security",
        user_goal="Report a suspicious phishing email to security team.",
        initial_complaint_hint="Received fake IT email asking to reset credentials.",
        fact_sheet={
            "sender": "IT-Support@payroll-verify.net (suspicious domain)",
            "content": "Link to fake login page asking for credentials",
            "action_taken": "Did not click the link",
            "scope": "Several colleagues received the same email",
            "urgency": "Urgent — possible phishing incident",
        },
        title_keywords=("phishing", "security", "email", "suspicious"),
        persona=_DEFAULT_PERSONA,
    ),
    LiveTicketScenario(
        id="infrastructure_wiki",
        category="infrastructure",
        user_goal="Restore access to internal Confluence wiki.",
        initial_complaint_hint="Internal wiki shows 502 Bad Gateway for everyone.",
        fact_sheet={
            "service": "https://wiki.company.internal (Confluence)",
            "symptom": "502 Bad Gateway",
            "when_started": "Since 10:15am",
            "scope": "Tested on VPN and office network — same for all users",
            "impact": "Teams cannot access runbooks during active deployment",
            "urgency": "High",
        },
        title_keywords=("confluence", "wiki", "502", "infrastructure", "internal"),
        persona=Persona(name="Casey Brooks", role="DevOps Engineer", department="Engineering"),
    ),
    LiveTicketScenario(
        id="hardware_printer",
        category="hardware",
        user_goal="Print to the 3rd floor HP printer again.",
        initial_complaint_hint="Network printer shows offline only for me.",
        fact_sheet={
            "device": "HP LaserJet Floor3",
            "symptom": "Shows offline in Windows; jobs stuck in queue",
            "error": "0x00000709",
            "when_started": "Since this morning",
            "note": "Colleagues on same floor can print fine",
            "urgency": "Normal",
        },
        title_keywords=("printer", "print", "hp", "hardware"),
        persona=_DEFAULT_PERSONA,
    ),
    LiveTicketScenario(
        id="network_wifi",
        category="network",
        user_goal="Fix Wi-Fi dropping during video calls in the east wing.",
        initial_complaint_hint="Corporate Wi-Fi disconnects every few minutes on video calls.",
        fact_sheet={
            "network": "Corporate SSID, east wing",
            "symptom": "Disconnects every 5–10 minutes; Teams calls freeze",
            "when_started": "After moving desks yesterday",
            "workaround": "Wired dock connection works",
            "impact": "Cannot attend video meetings reliably",
            "urgency": "Normal",
        },
        title_keywords=("wi-fi", "wifi", "network", "wireless", "teams"),
        persona=_DEFAULT_PERSONA,
    ),
    LiveTicketScenario(
        id="access_mfa",
        category="access_management",
        user_goal="Fix MFA so I can sign in to Okta SSO again.",
        initial_complaint_hint="Microsoft Authenticator codes rejected at SSO login.",
        fact_sheet={
            "apps": "Okta SSO, Microsoft Authenticator",
            "symptom": "Every MFA push and TOTP code rejected",
            "when_started": "Since this morning",
            "attempts": "Phone time synced; re-enrollment fails",
            "impact": "Cannot access email or internal apps — blocked from all work",
            "urgency": "High",
        },
        title_keywords=("mfa", "authenticator", "sso", "okta", "login", "access"),
        persona=_DEFAULT_PERSONA,
    ),
)
