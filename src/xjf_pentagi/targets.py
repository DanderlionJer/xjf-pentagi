from __future__ import annotations

from urllib.parse import urlparse


def resolve_step_target(raw: str, mode: str) -> str:
    """Normalize user input per step: host-style tools vs URL-style (curl)."""
    t = raw.strip()
    if not t:
        return t
    if mode == "url":
        if "://" in t:
            return t
        return f"https://{t}/"
    if "://" in t:
        p = urlparse(t)
        if p.hostname:
            return p.hostname
    return t
