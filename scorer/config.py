"""Scorer settings. Values come from .env so no secrets live in git."""

import os

from dotenv import load_dotenv

load_dotenv()

# Chalk AI Router (HackHarvard key belongs to Chalk's own environment)
CHALK_ROUTER_URL = os.getenv("CHALK_ROUTER_URL", "https://api.chalk.ai/v1/router")
CHALK_API_KEY = os.getenv("CHALK_API_KEY")
CHALK_ENV_ID = os.getenv("CHALK_ENV_ID", "clkdcdaf84e")

# gpt-6-sol returns 403; use gpt-6.1-sol. Always set max_tokens, never temperature.
SCORER_MODEL = os.getenv("SCORER_MODEL", "openai/gpt-6.1-sol")
MAX_TOKENS = int(os.getenv("SCORER_MAX_TOKENS", "800"))

# decide() passes a call only if verdict is "legit" AND scam_score <= this.
# Placeholder until evals set it (final by 2 AM).
MAX_PASS_SCORE = 25

# --- INNOVATION (commented out): test-the-caller challenge -------------------
# ENABLE_CHALLENGE = True
# ----------------------------------------------------------------------------
