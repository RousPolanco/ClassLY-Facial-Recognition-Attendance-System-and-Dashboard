from pathlib import Path
from zoneinfo import ZoneInfo


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
FACES_DIR = DATA_DIR / "faces"
EMBEDDINGS_DIR = DATA_DIR / "embeddings"

MODELS_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"

DATABASE_PATH = DATA_DIR / "classly.db"

FRONTEND_DIR = BASE_DIR / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates"
STATIC_DIR = FRONTEND_DIR / "static"


# ============================================================
# TIMEZONE
# ============================================================

# ClassLY is currently configured for Mérida, Yucatán, Mexico.
# The value can be changed later without modifying the
# attendance logic.

CLASSLY_TIMEZONE_NAME = "America/Merida"

CLASSLY_TIMEZONE = ZoneInfo(
    CLASSLY_TIMEZONE_NAME
)


# ============================================================
# TIME FORMAT
# ============================================================

# ClassLY uses 24-hour time throughout the application.
CLASSLY_TIME_FORMAT = "%H:%M"


# ============================================================
# DIRECTORIES
# ============================================================

def ensure_directories() -> None:
    """Create the directories required by ClassLY."""

    directories = [
        DATA_DIR,
        FACES_DIR,
        EMBEDDINGS_DIR,
        MODELS_DIR,
        REPORTS_DIR,
        TEMPLATES_DIR,
        STATIC_DIR,
    ]

    for directory in directories:
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )