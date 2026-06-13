"""Official Vendor Guidelines, Nuances, and Real-World Use Cases.

These profiles are injected into the EnvironmentContext to provide the models
with vendor-specific "self-awareness" of their strengths, recommended practices,
and constraints.
"""

from pathlib import Path

_PROFILES_DIR = Path(__file__).resolve().parent / "profiles"

def _load_profile(filename: str) -> str:
    path = _PROFILES_DIR / filename
    if path.is_file():
        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception:
            return ""
    return ""

def get_profile(provider: str) -> str:
    provider = provider.lower()
    if provider in ("claude", "anthropic"):
        return _load_profile("anthropic.md")
    elif provider in ("codex", "openai"):
        return _load_profile("openai.md")
    elif provider in ("agy", "gemini", "google"):
        return _load_profile("google.md")
    return ""
