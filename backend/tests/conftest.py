import os

# Tests always run in plain local mode — no Supabase, no real Gemini —
# whatever is in backend/.env. load_dotenv() never overrides variables
# that are already set, so setting them here, before the app is imported,
# wins.
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SECRET_KEY"] = ""
os.environ["GENERATOR"] = "mock"
