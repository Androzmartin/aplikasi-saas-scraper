"""URL normalisation and validation for project input."""
import ipaddress
import re
from typing import List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
_ALLOWED_SCHEMES = {"http", "https"}
_LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)


class InvalidUrlError(ValueError):
    """Raised when a submitted target URL cannot be used for scraping."""


def _is_private_host(host: str) -> bool:
    """Block loopback/link-local/private targets so the scraper is not an SSRF tool."""
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def normalize_url(raw: str) -> str:
    """Return a canonical http(s) URL, or raise InvalidUrlError."""
    if not raw or not raw.strip():
        raise InvalidUrlError("URL kosong")

    candidate = raw.strip()
    # Strip characters commonly pasted along with URLs from spreadsheets.
    candidate = candidate.strip("<>\"'`,;")

    if not _SCHEME_RE.match(candidate):
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    scheme = parsed.scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise InvalidUrlError(f"Skema '{parsed.scheme}' tidak didukung")

    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        raise InvalidUrlError("Host tidak ditemukan")
    if _is_private_host(host):
        raise InvalidUrlError("Alamat internal/privat tidak diizinkan")

    labels = host.split(".")
    try:
        ipaddress.ip_address(host)
        is_ip = True
    except ValueError:
        is_ip = False
    if not is_ip:
        if len(labels) < 2:
            raise InvalidUrlError("Domain tidak valid")
        if not all(_LABEL_RE.match(label) for label in labels):
            raise InvalidUrlError("Domain tidak valid")

    netloc = host
    if parsed.port and parsed.port not in (80, 443):
        netloc = f"{host}:{parsed.port}"

    path = parsed.path or "/"
    # Drop fragments and tracking-only query strings are kept as-is; fragments never
    # change the fetched document.
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def parse_url_list(raw_urls: List[str]) -> Tuple[List[str], List[dict]]:
    """Normalise a batch, de-duplicating and reporting per-URL rejections."""
    accepted: List[str] = []
    rejected: List[dict] = []
    seen = set()

    for raw in raw_urls:
        value = (raw or "").strip()
        if not value:
            continue
        try:
            normalized = normalize_url(value)
        except InvalidUrlError as exc:
            rejected.append({"url": value, "reason": str(exc)})
            continue
        key = normalized.rstrip("/").lower()
        if key in seen:
            rejected.append({"url": value, "reason": "Duplikat dalam batch ini"})
            continue
        seen.add(key)
        accepted.append(normalized)

    return accepted, rejected


def registered_domain(url: str) -> Optional[str]:
    host = (urlparse(url).hostname or "").lower()
    return host or None


def same_site(a: str, b: str) -> bool:
    ha, hb = registered_domain(a), registered_domain(b)
    if not ha or not hb:
        return False
    return ha == hb or ha == f"www.{hb}" or hb == f"www.{ha}"
