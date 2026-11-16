import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / 'instance'

load_dotenv(BASE_DIR / '.env')


def _parse_deadline(value):
    deadline = datetime.fromisoformat(value)
    if deadline.tzinfo is not None:
        # The app compares against naive local time, so convert to that.
        deadline = deadline.astimezone().replace(tzinfo=None)
    return deadline


def _load_secret_key():
    """Use SECRET_KEY from the environment, or a random key persisted in instance/."""
    key = os.environ.get('SECRET_KEY')
    if key:
        return key
    key_file = INSTANCE_DIR / 'secret_key'
    if key_file.exists():
        return key_file.read_text().strip()
    INSTANCE_DIR.mkdir(exist_ok=True)
    key = secrets.token_hex(32)
    key_file.write_text(key)
    return key


class Config:
    # Last moment (server local time) when participants can pick, change their
    # pick or edit their wishlist. Can be overridden with DEADLINE in .env.
    DEADLINE = _parse_deadline(os.environ.get('DEADLINE', '2026-12-15T23:59:59'))

    # Price range for presents, shown next to the deadline.
    GIFT_BUDGET = os.environ.get('GIFT_BUDGET', '25-30 euro')

    # PIN for the /admin page. Admin login is disabled while it is empty.
    ADMIN_PIN = os.environ.get('ADMIN_PIN', '')

    # Public address used in invite links, e.g. https://santa.example.com.
    # When empty, links use the address the admin page was opened with.
    PUBLIC_URL = os.environ.get('PUBLIC_URL', '').rstrip('/')

    SECRET_KEY = _load_secret_key()
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///santa.db')
    UPLOAD_FOLDER = str(BASE_DIR / 'static' / 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

    # Opening a personal link keeps the participant signed in for a year.
    PERMANENT_SESSION_LIFETIME = timedelta(days=365)
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE') == '1'
