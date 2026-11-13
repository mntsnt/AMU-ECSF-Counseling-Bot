import os
from pathlib import Path
from typing import Set, Optional

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

def load_env_file(filepath: Path = None) -> None:
    """
    Lightweight, dependency-free .env file parser.
    Populates os.environ if keys are not already set.
    """
    if filepath is None:
        filepath = BASE_DIR / ".env"
    
    if not filepath.exists():
        return

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    # Update or set
                    os.environ[key] = val
    except Exception as e:
        print(f"[Config] Notice: Could not read .env file: {e}")

# Load .env file automatically
load_env_file()

# Telegram Bot Token
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()

# Counselors Telegram User IDs
def parse_counselor_ids() -> Set[int]:
    """Parse comma, semicolon, or space-separated counselor user IDs."""
    raw = os.getenv("COUNSELOR_IDS") or os.getenv("ADMIN_IDS") or ""
    ids: Set[int] = set()
    for item in raw.replace(";", ",").split(","):
        clean_item = item.strip()
        if clean_item.lstrip("-").isdigit():
            ids.add(int(clean_item))
    return ids

COUNSELOR_IDS: Set[int] = parse_counselor_ids()

# Optional Counselor Team Group ID (e.g. -100xxxxxxxxxx)
def parse_counselor_group_id() -> Optional[int]:
    raw = os.getenv("COUNSELOR_GROUP_ID", "").strip()
    if raw.lstrip("-").isdigit():
        return int(raw)
    return None

COUNSELOR_GROUP_ID: Optional[int] = parse_counselor_group_id()

def reload_config() -> None:
    """Reload all configurations from .env at runtime."""
    global COUNSELOR_IDS, COUNSELOR_GROUP_ID, BOT_TOKEN
    load_env_file()
    COUNSELOR_IDS = parse_counselor_ids()
    COUNSELOR_GROUP_ID = parse_counselor_group_id()
    BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

def is_counselor(user_id: int) -> bool:
    """Check if given Telegram user_id is an authorized counselor."""
    return user_id in COUNSELOR_IDS

# Database Configuration
DATABASE_PATH: Path = BASE_DIR / os.getenv("DATABASE_PATH", "counseling_bot.db")

# Organization / Bot Branding Texts
BOT_NAME: str = os.getenv("BOT_NAME", "AMU-ECSF Counseling Bot")

WELCOME_MESSAGE: str = (
    "Welcome\n\n"
    f"Welcome to the {BOT_NAME}. Our team is ready to counsel you on your journey. "
    "We offer a safe and confidential space for you to explore your concerns.\n\n"
    "Here no one can know who you are.\n\n"
    "You are 100% safe.\n\n"
    "Please send your question or concern.\n\n"
    "#Spiritual #Family_Issue #Addiction #Relationships #Anxiety #Friendship "
    "#Decision_Making #Academic #Fear #Stress"
)

HELP_MESSAGE_USER: str = (
    "Counseling Bot Guide\n\n"
    "1. Complete Confidentiality: Your identity, username, and account details are completely hidden from counselors. "
    "You are identified only by an anonymous number.\n"
    "2. Submit Your Question: Send any text, voice note, or question directly here.\n"
    "3. Dedicated Counselor: An available counselor will select your case and chat with you directly.\n\n"
    "Commands:\n"
    "/start - View welcome message and instructions\n"
    "/status - Check your current case status\n"
    "/close - End your current counseling session\n"
    "/myid - View your numeric Telegram user ID\n"
    "/help - View this guide"
)

HELP_MESSAGE_COUNSELOR: str = (
    "Counselor Command Center\n\n"
    "Commands:\n"
    "/feed or /cases - View feed of new users waiting for counsel\n"
    "/active - View the user you are currently chatting with\n"
    "/close - Conclude and close your active counseling session\n"
    "/release - Return your active user back to the feed\n"
    "/stats - View counseling statistics\n"
    "/reload - Reload counselor IDs and settings from .env\n"
    "/myid - View your numeric Telegram user ID\n"
    "/help - Show this help menu\n\n"
    "How Counseling Works:\n"
    "1. When a seeker sends a message, it appears on your feed with a [Select User] button.\n"
    "2. Click [Select User] to begin chatting with that seeker anonymously.\n"
    "3. While connected, any message or voice note you send here is delivered directly to the user as 'Counselor'.\n"
    "4. When finished, send /close to conclude the session."
)
