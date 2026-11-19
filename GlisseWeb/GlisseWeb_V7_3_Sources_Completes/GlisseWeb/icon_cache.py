# -*- coding: utf-8 -*-
"""Chemins sûrs pour les favicons, issus de domaines web (jamais des chemins d'URL)."""
from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlsplit


def favicon_path(directory: Path, url: str) -> Path | None:
    """Renvoie un nom de fichier PNG stable ou None si l'URL n'est pas un site web."""
    try:
        parsed = urlsplit(url)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return None
        host = parsed.hostname.lower().rstrip(".")
        if not host:
            return None
        digest = hashlib.sha256(host.encode("utf-8")).hexdigest()
        return directory / f"{digest}.png"
    except (ValueError, UnicodeError):
        return None
