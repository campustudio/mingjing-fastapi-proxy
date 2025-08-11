# core/config.py
import os
CONTEXT_MAX_TURNS = int(os.getenv("CONTEXT_MAX_TURNS", "16"))