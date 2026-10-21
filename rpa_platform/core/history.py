"""Persistent execution history shared by the Orchestrator and scheduled runs."""

import json
import os
from typing import Dict, List

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
HISTORY_FILE = os.path.join(LOGS_DIR, "history.json")
MAX_ENTRIES = 500


def load_history() -> List[Dict]:
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def append_history(entry: Dict):
    """entry: {name, state (success|failed|stopped), elapsed, ts, origin}"""
    os.makedirs(LOGS_DIR, exist_ok=True)
    entries = load_history()
    entries.append(entry)
    tmp = HISTORY_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(entries[-MAX_ENTRIES:], f, ensure_ascii=False, indent=2)
    os.replace(tmp, HISTORY_FILE)
