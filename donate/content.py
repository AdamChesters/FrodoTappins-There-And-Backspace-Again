"""Canonical bundled copy and app-specific adapter identity."""
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable, Any

CONTENT = json.loads((Path(__file__).parent / 'content.json').read_text(encoding='utf-8'))

@dataclass
class SupportIdentity:
    appName: str
    appLogo: Any
    appVersion: str
    appId: str
    checkForUpdates: Callable[[], None]
