"""Load repository-local settings without replacing real environment variables."""
from pathlib import Path
from app.paths import REPOSITORY_ROOT


def load_dotenv(path, override=False):
    """Dotenv is needed only when a local settings file actually exists."""
    if not Path(path).is_file():
        return False
    try:
        from dotenv import load_dotenv as read_dotenv
    except ModuleNotFoundError as exc:
        if exc.name != 'dotenv':
            raise
        raise RuntimeError('Local .env exists but python-dotenv is missing. Install requirements.txt.') from None
    return read_dotenv(path, override=override)


def load_environment():
    """Read only the repository root .env, independent of working directory."""
    return load_dotenv(REPOSITORY_ROOT / '.env', override=False)
