"""
q-config.py — Shared config loader for all Q scripts.
Pure stdlib. No external dependencies.
"""

import json
import os
import sys
from pathlib import Path


def find_repo_root() -> Path:
    """Walk up from the script location to find the repo root (where q-config.json lives)."""
    start = Path(__file__).resolve().parent
    current = start
    while current != current.parent:
        if (current / "q-config.json").exists():
            return current
        current = current.parent
    # Fallback: assume repo root is two levels up from scripts/
    return Path(__file__).resolve().parent.parent


def load_config() -> dict:
    """Load q-config.json from repo root. Returns config dict."""
    root = find_repo_root()
    config_path = root / "q-config.json"

    if not config_path.exists():
        print(f"[Q ERROR] q-config.json not found at {config_path}", file=sys.stderr)
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Resolve relative paths to absolute
    config["_root"] = str(root)
    config["kb_path"] = str(root / config.get("kb_path", "knowledge_base"))
    config["verdicts_path"] = str(root / config.get("verdicts_path", "knowledge_base/verdicts/index.md"))
    config["learned_path"] = str(root / config.get("learned_path", "knowledge_base/learned/q-learned.md"))

    return config


def get_api_key(config: dict) -> str:
    """Retrieve Anthropic API key from environment variable specified in config."""
    env_var = config.get("anthropic_api_key_env", "ANTHROPIC_API_KEY")
    key = os.environ.get(env_var, "")
    if not key:
        print(f"[Q ERROR] API key not found. Set environment variable: {env_var}", file=sys.stderr)
        sys.exit(1)
    return key


def get_model(config: dict, force_fast: bool = False) -> str:
    """Return the appropriate model based on config mode."""
    if force_fast or config.get("mode") == "fast":
        return config.get("model_fast", "claude-haiku-4-5-20251001")
    return config.get("model_normal", "claude-sonnet-4-6")


def should_watch_file(config: dict, file_path: str) -> bool:
    """Return True if Q should judge this file based on extension and exclude patterns."""
    import fnmatch

    path = Path(file_path)

    # Check extension
    watched = config.get("watched_extensions", [])
    if watched and path.suffix.lower() not in watched:
        return False

    # Check exclude patterns
    for pattern in config.get("exclude_patterns", []):
        # Normalize path for pattern matching
        normalized = file_path.replace("\\", "/")
        if fnmatch.fnmatch(normalized, pattern):
            return False

    return True


def sensitivity_allows(config: dict, severity: str) -> bool:
    """Return True if the given severity should be surfaced based on sensitivity setting."""
    sensitivity = config.get("sensitivity", "normal")
    p3_silent = config.get("p3_silent", True)

    order = ["P0", "P1", "P2", "P3"]
    thresholds = {
        "strict": "P3",
        "normal": "P2",
        "quiet": "P1",
        "silent": "P0",
    }

    threshold = thresholds.get(sensitivity, "P2")

    # P3 always silent if p3_silent is set
    if severity == "P3" and p3_silent:
        return False

    threshold_idx = order.index(threshold)
    severity_idx = order.index(severity) if severity in order else 99

    return severity_idx <= threshold_idx
