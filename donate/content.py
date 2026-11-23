"""Canonical bundled copy and app-specific adapter identity."""
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable, Optional

CONTENT = json.loads((Path(__file__).parent / 'content.json').read_text(encoding='utf-8'))

@dataclass
class SupportIdentity:
    appName: str
    appLogo: Any
    appVersion: str
    appId: str
    checkForUpdates: Callable[[], None]
    # Optional host hooks: cancel a running update; build the host's own window
    # chrome for a dialog and return the layout that takes its content.
    cancelUpdate: Optional[Callable[[], None]] = None
    frame: Optional[Callable[[Any, str], Any]] = None
