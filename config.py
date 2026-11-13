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

# Webhook configuration (for serverless deployments like Vercel)
WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "").strip()

def reload_config() -> None:
    """Reload all configurations from .env at runtime."""
    global COUNSELOR_IDS, COUNSELOR_GROUP_ID, BOT_TOKEN, WEBHOOK_URL
    load_env_file()
    COUNSELOR_IDS = parse_counselor_ids()
    COUNSELOR_GROUP_ID = parse_counselor_group_id()
    BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()

def is_counselor(user_id: int) -> bool:
    """Check if given Telegram user_id is an authorized counselor."""
    return user_id in COUNSELOR_IDS

# Serverless environment detection (e.g. Vercel, AWS Lambda)
IS_SERVERLESS: bool = bool(
    os.getenv("VERCEL") 
    or os.getenv("AWS_LAMBDA_FUNCTION_NAME") 
    or os.getenv("SERVERLESS")
)

# Database Configuration (uses /tmp on serverless where root is read-only)
if IS_SERVERLESS:
    DATABASE_PATH: Path = Path("/tmp") / os.getenv("DATABASE_PATH", "counseling_bot.db")
else:
    DATABASE_PATH: Path = BASE_DIR / os.getenv("DATABASE_PATH", "counseling_bot.db")

# Organization / Bot Branding Texts
BOT_NAME: str = os.getenv("BOT_NAME", "AMU-ECSF Counseling Bot")

WELCOME_MESSAGE: str = (
    "👤 Welcome\n\n"
    f"🌿 Welcome to the {BOT_NAME}. Our team is ready to counsel you on your journey. "
    "We offer a safe and confidential space for you to explore your concerns.\n\n"
    "🔗 Here no one can know who you are 🔗\n\n"
    "🎖 You are 100% safe\n\n"
    "Please send your question or concern.\n\n"
    "#Spiritual #Family_Issue #Addiction #Relationships #Anxiety #Friendship "
    "#Decision_Making #Academic #Fear #Stress"
)

HELP_MESSAGE_USER: str = (
    "ℹ️ Counseling Bot Guide\n\n"
    "🔒 Complete Confidentiality: Your identity, username, and account details are completely hidden from counselors. "
    "You are identified only by an anonymous case number.\n\n"
    "✍️ Submit Your Question: Send any text, voice note, or media directly to this bot.\n\n"
    "🤝 Dedicated Counselor: An available counselor will claim your case from the queue and chat with you directly.\n\n"
    "Commands:\n"
    "/start - Restart the bot and view instructions\n"
    "/status - Check your current counseling status\n"
    "/close - Conclude your counseling session\n"
    "/help - Show this guide"
)

HELP_MESSAGE_COUNSELOR: str = (
    "🛠 Counselor Command Center\n\n"
    "Commands & Navigation:\n"
    "📥 /feed - View queue of waiting seekers and select one to chat\n"
    "💬 /active - View the seeker you are currently counseling\n"
    "❌ /close - Conclude and close your active session\n"
    "↩️ /release - Return your active seeker back to the feed\n"
    "📊 /stats - View counseling statistics\n"
    "🔄 /reload - Reload counselor IDs from .env\n"
    "ℹ️ /help - Show this guide\n\n"
    "Workflow:\n"
    "1. When a seeker submits a question, it appears in your feed.\n"
    "2. Click 'Chat with User' to establish an anonymous connection.\n"
    "3. While connected, all messages you send are delivered to the seeker as 'Counselor'.\n"
    "4. When finished, use /close or the 'End Session' button."
)
