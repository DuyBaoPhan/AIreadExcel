"""Load repository-local settings without replacing real environment variables."""
from pathlib import Path
from dotenv import load_dotenv


def load_environment():
    """Read only the repository root .env, independent of working directory."""
    return load_dotenv(Path(__file__).resolve().parents[3] / '.env', override=False)
