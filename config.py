"""Central configuration. Reads everything from .env via python-dotenv."""
import os
from dotenv import load_dotenv

load_dotenv()


def _parse_admin_ids(raw: str) -> list[int]:
    ids: list[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if chunk:
            try:
                ids.append(int(chunk))
            except ValueError:
                continue
    return ids


BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_IDS: list[int] = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))
ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")

raw_db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot_data.db")
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif raw_db_url.startswith("postgresql://") and not raw_db_url.startswith("postgresql+asyncpg://"):
    raw_db_url = raw_db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

DATABASE_URL: str = raw_db_url

REMINDER_INTERVAL_MIN: int = int(os.getenv("REMINDER_INTERVAL_MIN", "10"))
REMINDER_DELAY_MIN: int = int(os.getenv("REMINDER_DELAY_MIN", "30"))
DROP_OFF_HOURS: int = int(os.getenv("DROP_OFF_HOURS", "24"))

DAILY_REPORT_HOUR: int = int(os.getenv("DAILY_REPORT_HOUR", "21"))
DAILY_REPORT_MIN: int = int(os.getenv("DAILY_REPORT_MIN", "0"))

# Timezone for scheduler (default Asia/Tashkent = UTC+5)
SCHEDULER_TZ: str = os.getenv("SCHEDULER_TZ", "Asia/Tashkent")

FLOOD_LIMIT: int = int(os.getenv("FLOOD_LIMIT", "10"))
FLOOD_WINDOW_SEC: int = int(os.getenv("FLOOD_WINDOW_SEC", "60"))
FLOOD_BAN_MIN: int = int(os.getenv("FLOOD_BAN_MIN", "5"))


def is_admin(user_id: int) -> bool:
    """Check whether a Telegram user id is in the admin whitelist.

    For backward compatibility only — actual role-aware checks should use
    `is_admin_async` / `get_admin_role_async` from utils.security.
    """
    return user_id in ADMIN_IDS
