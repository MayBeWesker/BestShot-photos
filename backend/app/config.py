from pathlib import Path
import os


APP_NAME = "BestShot-photos"
MAX_IMAGE_EDGE = 6000
MAX_IMAGE_PIXELS = 40_000_000
# The organizer processes one image at a time and stores the untouched upload,
# so it can safely accept modern panoramic/48 MP phone photos. The merge tool
# keeps the lower limits because composition creates several full-size copies.
ORGANIZER_MAX_IMAGE_EDGE = 12000
ORGANIZER_MAX_IMAGE_PIXELS = 80_000_000
MAX_UPLOAD_BYTES = 40 * 1024 * 1024
MAX_VERSIONS = 10
WORKING_MAX_EDGE = 1800

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_local_env() -> None:
    """Load simple KEY=VALUE entries from the ignored project-local .env file."""
    path = PROJECT_ROOT / ".env"
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_local_env()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-flash").strip()
DATA_ROOT = Path(os.getenv("BESTSHOT_DATA_DIR", PROJECT_ROOT / ".bestshot-data")).resolve()
DATA_ROOT.mkdir(parents=True, exist_ok=True)

