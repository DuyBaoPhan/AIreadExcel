"""Stable filesystem layout shared by launchers and application services.

Resolve from this module rather than the working directory or service depth.
Runtime data stays in its existing location to preserve deployed workspaces.
"""
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
ENGINE_DIR = APP_DIR.parent
REPOSITORY_ROOT = ENGINE_DIR.parent
PROJECTS_DIR = ENGINE_DIR / "projects"
DATABASE_PATH = ENGINE_DIR / "excel_rule_engine.db"
UI_DIR = APP_DIR / "ui"
