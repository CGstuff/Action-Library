"""
Identity - Per-machine user identity for Action Library.

Stores who the local user is (name, display name, color) for attributing
notes, drawings, and other actions in the shared library. Identity lives
ONLY on the local machine — the shared library never sees it as a setting.

This decoupling is what prevents the "two artists pointed at the same
network library overwrite each other's selection" bug that was reported
on Discord and previously fixed at the Settings level. With Option B, the
shared user roster goes away entirely; identity is local-config-only.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


# 12 distinguishable colors. Generated colors come from this palette so that
# every machine assigns the same color to the same name (deterministic by hash).
# Palette is curated for visual distinction at small sizes (avatar pills, stroke
# author indicators); avoid near-duplicates and very dark/light shades.
COLOR_PALETTE = [
    "#E91E63",  # pink
    "#9C27B0",  # purple
    "#673AB7",  # deep purple
    "#3F51B5",  # indigo
    "#2196F3",  # blue
    "#00BCD4",  # cyan
    "#009688",  # teal
    "#4CAF50",  # green
    "#FF9800",  # orange
    "#FF5722",  # deep orange
    "#795548",  # brown
    "#607D8B",  # blue grey
]


# Username sanitization: lowercase, allow [a-z0-9_-], collapse other runs to '_'
_USERNAME_INVALID = re.compile(r"[^a-z0-9_-]+")


@dataclass(frozen=True)
class Identity:
    """
    Per-machine user identity.

    Attributes:
        name: Short username used in attribution fields (e.g. "alice").
              Lowercase, alphanumeric + underscore + hyphen only.
        display_name: Human-readable label shown in the UI (e.g. "Alice Chen").
                      Free-form, may contain spaces and unicode.
        color: Hex color string, used for the user's avatar pill and stroke
               attribution colors (e.g. "#E91E63").
    """

    name: str
    display_name: str
    color: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional["Identity"]:
        """
        Deserialize from a dict. Returns None if the dict is malformed.

        Tolerant of missing or empty fields — caller decides whether None
        means "no identity" or "fall back to wizard."
        """
        if not isinstance(data, dict):
            return None
        name = data.get("name")
        display_name = data.get("display_name")
        color = data.get("color")
        if not isinstance(name, str) or not name:
            return None
        if not isinstance(display_name, str) or not display_name:
            return None
        if not isinstance(color, str) or not color:
            return None
        return cls(name=name, display_name=display_name, color=color)


def sanitize_username(raw: str) -> str:
    """
    Sanitize a raw string into a valid username.

    Lowercases, replaces invalid character runs with a single underscore,
    strips leading/trailing underscores. Returns "" if nothing usable
    remains.

    Examples:
        "Alice Chen"   -> "alice_chen"
        "alice@123"    -> "alice_123"
        "Bob's Rig!"   -> "bob_s_rig"
        "   "          -> ""
    """
    if not raw:
        return ""
    cleaned = _USERNAME_INVALID.sub("_", raw.strip().lower())
    return cleaned.strip("_")


def generate_color_from_name(name: str) -> str:
    """
    Pick a deterministic color from COLOR_PALETTE based on the username.

    Same name always maps to same color across machines. Uses MD5 (not for
    security — just for stable hashing across Python versions).
    """
    if not name:
        return COLOR_PALETTE[0]
    digest = hashlib.md5(name.lower().encode("utf-8")).hexdigest()
    index = int(digest, 16) % len(COLOR_PALETTE)
    return COLOR_PALETTE[index]


__all__ = [
    "Identity",
    "COLOR_PALETTE",
    "sanitize_username",
    "generate_color_from_name",
]
