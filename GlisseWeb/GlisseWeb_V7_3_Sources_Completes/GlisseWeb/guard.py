# -*- coding: utf-8 -*-
"""Regles independantes de Qt : adresses, navigation, noms de telechargements.
La protection anti-phishing et l'analyse antivirus relevent toujours du systeme
et/ou d'un navigateur majeur maintenu, pas de ce petit module.
"""
from __future__ import annotations

import ipaddress
import re
from pathlib import PurePath
from urllib.parse import quote_plus, urlsplit

HOME = "https://www.google.com/"
SEARCH = "https://www.google.com/search?q="
DANGEROUS_EXTENSIONS = {
    ".exe", ".com", ".scr", ".bat", ".cmd", ".ps1", ".psm1",
    ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh", ".hta", ".msi",
    ".msp", ".reg", ".lnk", ".url", ".jar", ".iso", ".img",
    ".dll", ".cpl", ".appx", ".msix", ".msixbundle",
}
_DOMAIN = re.compile(r"^(?=.{1,253}$)(?:[a-zA-Z0-9-]{1,63}\.)+[a-zA-Z0-9-]{2,63}$")


def query_to_url(raw: str) -> str:
    value = raw.strip()
    if not value:
        return HOME
    if value == "about:blank":
        return value
    if any(ord(ch) < 32 for ch in value):
        return SEARCH + quote_plus(value)
    try:
        parsed = urlsplit(value)
    except ValueError:
        return SEARCH + quote_plus(value)
    if parsed.scheme.lower() in ("https", "http"):
        try:
            return value if parsed.hostname else SEARCH + quote_plus(value)
        except ValueError:
            return SEARCH + quote_plus(value)
    if any(ch.isspace() for ch in value) or "@" in value:
        return SEARCH + quote_plus(value)
    host_port = value.split("/", 1)[0]
    host = host_port.split(":", 1)[0]
    # localhost:1234 n'est pas un protocole, c'est une adresse locale.
    if parsed.scheme and host.lower() != "localhost" and not _DOMAIN.fullmatch(host):
        return SEARCH + quote_plus(value)
    try:
        ipaddress.ip_address(host.strip("[]"))
        is_ip = True
    except ValueError:
        is_ip = False
    if host.lower() == "localhost" or is_ip:
        return "http://" + value
    # Domaines ASCII ou IDN selon les regles de Python (pas d'execution de code).
    try:
        host_ascii = host.encode("idna").decode("ascii")
    except UnicodeError:
        host_ascii = ""
    if _DOMAIN.fullmatch(host_ascii) and not host.startswith("."):
        return "https://" + value
    return SEARCH + quote_plus(value)


def is_allowed_main_url(raw: str) -> bool:
    """Bloque file:, javascript:, data:, chrome:, ftp: et tout protocole non web."""
    if raw == "about:blank":
        return True
    try:
        url = urlsplit(raw)
        return url.scheme.lower() in ("http", "https") and bool(url.hostname)
    except ValueError:
        return False


def suspicious_download(filename: str) -> bool:
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].rstrip(". ").lower()
    # Ex. facture.pdf.exe ou note.docx.js : seule la derniere extension execute.
    return PurePath(name).suffix in DANGEROUS_EXTENSIONS


def display_host(raw: str) -> str:
    try:
        return urlsplit(raw).hostname or ""
    except ValueError:
        return ""
