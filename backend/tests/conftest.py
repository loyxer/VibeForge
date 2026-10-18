import os

# Tests always run in plain local mode — no Supabase, no real Gemini —
# whatever is in backend/.env. load_dotenv() never overrides variables
# that are already set, so setting them here, before the app is imported,
# wins.
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SECRET_KEY"] = ""
os.environ["GENERATOR"] = "mock"
os.environ["TELEGRAM_BOT_TOKEN"] = ""  # never talk to the real bot
os.environ["RENDER_EXTERNAL_URL"] = ""

import pytest  # noqa: E402

from app import user_photos  # noqa: E402


@pytest.fixture(autouse=True)
def temp_photo_store(tmp_path, monkeypatch):
    """Uploaded photos go to a temporary folder, never backend/data."""
    monkeypatch.setattr(user_photos, "_STORE_PATH", tmp_path / "photos.json")
    monkeypatch.setattr(user_photos, "_UPLOADS", tmp_path / "uploads")


@pytest.fixture(autouse=True)
def temp_visit_store(tmp_path, monkeypatch):
    from app import leads, visits

    monkeypatch.setattr(visits, "_STORE_PATH", tmp_path / "visits.json")
    monkeypatch.setattr(leads, "_LEADS_PATH", tmp_path / "leads.json")
    monkeypatch.setattr(leads, "_LINKS_PATH", tmp_path / "telegram.json")
    visits._sites.clear()
    visits._last_seen.clear()


@pytest.fixture(autouse=True)
def temp_review_store(tmp_path, monkeypatch):
    from app import reviews

    monkeypatch.setattr(reviews, "_PATH", tmp_path / "reviews.json")
    reviews._recent.clear()
