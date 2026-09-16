"""Extract publicly displayed business contact data from crawled HTML pages.

Only information a visitor can already read on the public page is collected:
business name, public phone/WhatsApp, public email, address and a contact person
when the page states one. Nothing is inferred from private sources.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup

from app.services.regions import detect_region

# --------------------------------------------------------------------------- regex

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", re.IGNORECASE
)

# Indonesian numbers: +62..., 62..., 08... with optional separators.
PHONE_RE = re.compile(
    r"(?:(?<![\w])(?:\+?62|0)[\s.\-()]?(?:\d[\s.\-()]?){7,13}\d)"
)

WA_LINK_RE = re.compile(
    r"(?:wa\.me|api\.whatsapp\.com|web\.whatsapp\.com|whatsapp\.com/send)[^\s\"'<>]*",
    re.IGNORECASE,
)

_PHONE_LABEL_HINTS = ("telp", "telepon", "phone", "tel.", "hp", "hubungi", "call", "kontak")
_WA_LABEL_HINTS = ("whatsapp", "wa ", "wa:", "chat wa", "via wa", "wa/")

_ADDRESS_HINTS = (
    "jl.", "jl ", "jalan ", "ruko", "gedung", "komplek", "kompleks", "perumahan",
    "alamat", "kel.", "kec.", "kelurahan", "kecamatan", "blok", "lantai", "lt.",
    "no.", "rt ", "rw ", "plaza", "tower", "mall",
)

# The label is matched case-insensitively, but the name itself must be
# capitalised — that is what separates a real person from surrounding prose.
_PERSON_LABEL_RE = re.compile(
    r"(?i:contact\s*person|narahubung|\bcp\b|\bpic\b|owner|pemilik|founder)"
    r"[ \t]*[:\-\u2013][ \t]*"
    r"(?:(?i:bapak|ibu|bpk|mr|mrs|ms|pak|bu)\.?[ \t]+)?"
    # Spaces/tabs only between name words: a newline ends the name, so a label on
    # the following line is never absorbed into it.
    r"([A-Z][a-zA-Z'\.]+(?:[ \t]+[A-Z][a-zA-Z'\.]+){0,3})"
)

_ROLE_WORDS = {
    "owner", "founder", "director", "ceo", "manager", "admin", "marketing",
    "sales", "pemilik", "direktur", "pengelola",
}

_GENERIC_EMAIL_LOCALPARTS = {
    "example", "email", "your", "yourname", "name", "user", "test", "sample",
    "domain", "someone", "nama",
}

_BAD_EMAIL_DOMAINS = {
    "example.com", "example.org", "domain.com", "email.com", "sentry.io",
    "wixpress.com", "godaddy.com", "sentry-cdn.com", "w3.org", "schema.org",
}

_IMAGE_EXT_RE = re.compile(r"\.(png|jpe?g|gif|svg|webp|ico|bmp|css|js)$", re.IGNORECASE)

_NAME_NOISE_RE = re.compile(
    r"\s*[|\-–—•·]\s*(home|beranda|official\s*website|website\s*resmi|selamat\s*datang"
    r"|welcome|homepage)\s*$",
    re.IGNORECASE,
)


@dataclass
class ExtractedContact:
    """Aggregated contact data plus per-field provenance and confidence."""

    business_name: Optional[str] = None
    whatsapp_number: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    contact_person: Optional[str] = None
    region: str = "unknown"
    source_page: Optional[str] = None
    field_sources: Dict[str, str] = field(default_factory=dict)
    field_confidence: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "business_name": self.business_name,
            "whatsapp_number": self.whatsapp_number,
            "phone_number": self.phone_number,
            "email": self.email,
            "address": self.address,
            "contact_person": self.contact_person,
            "region": self.region,
            "source_page": self.source_page,
            "field_sources": self.field_sources,
            "field_confidence": self.field_confidence,
        }


# ------------------------------------------------------------------ normalisation


def normalize_phone(raw: str) -> Optional[str]:
    """Normalise an Indonesian phone number to +62XXXXXXXXXX, or None if implausible."""
    if not raw:
        return None
    digits = re.sub(r"[^\d+]", "", raw)
    if digits.startswith("+"):
        digits = "+" + re.sub(r"\D", "", digits[1:])
    else:
        digits = re.sub(r"\D", "", digits)

    if digits.startswith("+62"):
        national = digits[3:]
    elif digits.startswith("62"):
        national = digits[2:]
    elif digits.startswith("0"):
        national = digits[1:]
    else:
        # Bare national number (e.g. "81234567890") is only accepted when it looks
        # like an Indonesian mobile prefix.
        national = digits
        if not national.startswith("8"):
            return None

    national = national.lstrip("0")
    if not national.isdigit():
        return None
    # Indonesian national numbers run 8-12 digits (mobile) / 8-11 (landline+area).
    if not (8 <= len(national) <= 13):
        return None
    return f"+62{national}"


def is_mobile(number: Optional[str]) -> bool:
    """True when a normalised +62 number is a mobile line (WhatsApp-capable)."""
    if not number or not number.startswith("+62"):
        return False
    return number[3:].startswith("8")


def clean_business_name(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    name = re.sub(r"\s+", " ", raw).strip(" \t\n\r-|•·—–")
    name = _NAME_NOISE_RE.sub("", name).strip(" -|•·—–")
    if len(name) < 2 or len(name) > 120:
        return None
    return name


def is_valid_public_email(email: str) -> bool:
    email = email.strip().lower()
    if not EMAIL_RE.fullmatch(email):
        return False
    if _IMAGE_EXT_RE.search(email):
        return False
    local, _, domain = email.partition("@")
    if domain in _BAD_EMAIL_DOMAINS:
        return False
    if local in _GENERIC_EMAIL_LOCALPARTS:
        return False
    # Hashed asset names such as logo@2x.png-style artefacts.
    if len(local) > 64 or len(domain) > 190:
        return False
    return True


# ---------------------------------------------------------------------- extraction


def _jsonld_blocks(soup: BeautifulSoup) -> Iterable[Dict[str, Any]]:
    for tag in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        raw = tag.string or tag.get_text() or ""
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                yield node
                stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
            elif isinstance(node, list):
                stack.extend(item for item in node if isinstance(item, (dict, list)))


def _flatten_address(node: Any) -> Optional[str]:
    if isinstance(node, str):
        return node.strip() or None
    if isinstance(node, dict):
        parts = [
            node.get("streetAddress"),
            node.get("addressLocality"),
            node.get("addressRegion"),
            node.get("postalCode"),
        ]
        joined = ", ".join(str(p).strip() for p in parts if p)
        return joined or None
    return None


def extract_from_structured_data(soup: BeautifulSoup) -> Dict[str, Any]:
    """Pull business fields out of schema.org JSON-LD when the site publishes it."""
    found: Dict[str, Any] = {}
    for block in _jsonld_blocks(soup):
        block_type = block.get("@type")
        types = {block_type} if isinstance(block_type, str) else set(block_type or [])
        types = {str(t).lower() for t in types}
        is_org = bool(
            types & {"organization", "localbusiness", "store", "restaurant", "corporation"}
        ) or any("business" in t for t in types)

        if is_org or "name" in block:
            if is_org and not found.get("business_name") and isinstance(block.get("name"), str):
                found["business_name"] = clean_business_name(block["name"])
            if not found.get("phone_number"):
                phone = block.get("telephone") or block.get("phone")
                if isinstance(phone, str):
                    normalized = normalize_phone(phone)
                    if normalized:
                        found["phone_number"] = normalized
            if not found.get("email") and isinstance(block.get("email"), str):
                candidate = block["email"].replace("mailto:", "").strip().lower()
                if is_valid_public_email(candidate):
                    found["email"] = candidate
            if not found.get("address"):
                address = _flatten_address(block.get("address"))
                if address:
                    found["address"] = re.sub(r"\s+", " ", address)[:300]
    return found


def extract_business_name(soup: BeautifulSoup, url: str) -> Optional[str]:
    og_site = soup.find("meta", attrs={"property": "og:site_name"})
    if og_site and og_site.get("content"):
        name = clean_business_name(og_site["content"])
        if name:
            return name

    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        name = clean_business_name(og_title["content"].split("|")[0].split(" - ")[0])
        if name:
            return name

    if soup.title and soup.title.string:
        name = clean_business_name(soup.title.string.split("|")[0].split(" - ")[0])
        if name:
            return name

    h1 = soup.find("h1")
    if h1:
        name = clean_business_name(h1.get_text(" ", strip=True))
        if name:
            return name

    host = (urlparse(url).hostname or "").replace("www.", "")
    if host:
        return clean_business_name(host.split(".")[0].replace("-", " ").title())
    return None


def extract_emails(soup: BeautifulSoup, text: str) -> List[str]:
    found: List[str] = []

    for link in soup.select('a[href^="mailto:"]'):
        href = link.get("href", "")
        candidate = unquote(href[7:].split("?")[0]).strip().lower()
        if is_valid_public_email(candidate) and candidate not in found:
            found.append(candidate)

    for match in EMAIL_RE.findall(text):
        candidate = match.strip().lower()
        if is_valid_public_email(candidate) and candidate not in found:
            found.append(candidate)

    return found


def extract_whatsapp(soup: BeautifulSoup, html: str, text: str) -> Optional[str]:
    """WhatsApp links are the strongest signal; fall back to labelled text."""
    for match in WA_LINK_RE.findall(html):
        # wa.me/6281..., api.whatsapp.com/send?phone=6281...
        phone_param = re.search(r"phone=(\+?\d{8,17})", match)
        raw = phone_param.group(1) if phone_param else None
        if not raw:
            path_digits = re.search(r"wa\.me/(\+?\d{8,17})", match, re.IGNORECASE)
            raw = path_digits.group(1) if path_digits else None
        if raw:
            normalized = normalize_phone(raw)
            if normalized:
                return normalized

    lowered = text.lower()
    for hint in _WA_LABEL_HINTS:
        idx = lowered.find(hint)
        while idx != -1:
            window = text[idx : idx + 120]
            for candidate in PHONE_RE.findall(window):
                normalized = normalize_phone(candidate)
                if normalized and is_mobile(normalized):
                    return normalized
            idx = lowered.find(hint, idx + 1)
    return None


def extract_phones(soup: BeautifulSoup, text: str) -> List[str]:
    numbers: List[str] = []

    for link in soup.select('a[href^="tel:"]'):
        raw = unquote(link.get("href", "")[4:])
        normalized = normalize_phone(raw)
        if normalized and normalized not in numbers:
            numbers.append(normalized)

    lowered = text.lower()
    for hint in _PHONE_LABEL_HINTS:
        idx = lowered.find(hint)
        while idx != -1:
            window = text[idx : idx + 120]
            for candidate in PHONE_RE.findall(window):
                normalized = normalize_phone(candidate)
                if normalized and normalized not in numbers:
                    numbers.append(normalized)
            idx = lowered.find(hint, idx + 1)

    for candidate in PHONE_RE.findall(text):
        normalized = normalize_phone(candidate)
        if normalized and normalized not in numbers:
            numbers.append(normalized)

    return numbers


def extract_address(soup: BeautifulSoup, text: str) -> Optional[str]:
    address_tag = soup.find("address")
    if address_tag:
        value = re.sub(r"\s+", " ", address_tag.get_text(" ", strip=True))
        if 10 <= len(value) <= 300:
            return value

    best: Optional[Tuple[int, str]] = None
    for raw_line in re.split(r"[\n\r]+", text):
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not (15 <= len(line) <= 250):
            continue
        lowered = line.lower()
        score = sum(2 for hint in _ADDRESS_HINTS if hint in lowered)
        if score == 0:
            continue
        if detect_region(line) not in ("unknown", "other"):
            score += 4
        if re.search(r"\b\d{5}\b", line):  # Indonesian postal code
            score += 2
        if best is None or score > best[0]:
            best = (score, line)

    return best[1] if best else None


def extract_contact_person(text: str) -> Optional[str]:
    for match in _PERSON_LABEL_RE.finditer(text):
        name = re.sub(r"\s+", " ", match.group(1)).strip(" .")
        words = name.split()
        if not words or len(words) > 4:
            continue
        if any(word.lower() in _ROLE_WORDS for word in words):
            continue
        if len(name) < 3 or len(name) > 60:
            continue
        if any(char.isdigit() for char in name):
            continue
        return name
    return None


def page_text(soup: BeautifulSoup) -> str:
    """Visible text only — scripts and styles are stripped."""
    clone = BeautifulSoup(str(soup), "lxml")
    for tag in clone(["script", "style", "noscript", "template"]):
        tag.decompose()
    return clone.get_text("\n", strip=True)


def extract_from_page(html: str, url: str) -> Dict[str, Any]:
    """Extract every supported field from a single page."""
    soup = BeautifulSoup(html, "lxml")
    text = page_text(soup)

    structured = extract_from_structured_data(soup)
    emails = extract_emails(soup, text)
    phones = extract_phones(soup, text)
    whatsapp = extract_whatsapp(soup, html, text)

    phone_number = structured.get("phone_number")
    if not phone_number:
        # Prefer a number that is not the WhatsApp one so both fields stay useful.
        non_wa = [p for p in phones if p != whatsapp]
        phone_number = (non_wa or phones or [None])[0]

    if not whatsapp:
        mobile = next((p for p in phones if is_mobile(p)), None)
        if mobile:
            whatsapp = mobile

    address = structured.get("address") or extract_address(soup, text)

    return {
        "business_name": structured.get("business_name") or extract_business_name(soup, url),
        "business_name_from_structured": bool(structured.get("business_name")),
        "whatsapp_number": whatsapp,
        "phone_number": phone_number,
        "email": structured.get("email") or (emails[0] if emails else None),
        "email_from_structured": bool(structured.get("email")),
        "address": address,
        "address_from_structured": bool(structured.get("address")),
        "contact_person": extract_contact_person(text),
        "all_emails": emails,
        "all_phones": phones,
        "source_url": url,
        "text_length": len(text),
    }


# Pages later in a crawl are usually contact/about pages, whose data is more
# authoritative than the homepage's — but the homepage names the business best.
_CONFIDENCE = {
    "structured": 0.95,
    "link": 0.9,
    "labelled": 0.75,
    "text": 0.6,
    "derived": 0.4,
}


def merge_page_results(results: List[Dict[str, Any]]) -> ExtractedContact:
    """Combine per-page extractions into one lead record with provenance."""
    contact = ExtractedContact()
    if not results:
        return contact

    contact.source_page = results[0].get("source_url")

    def take(field_name: str, value: Any, source_url: str, confidence: float) -> None:
        if value and not getattr(contact, field_name):
            setattr(contact, field_name, value)
            contact.field_sources[field_name] = source_url
            contact.field_confidence[field_name] = confidence

    # Business name: the first page (the submitted URL) is the best source.
    first = results[0]
    take(
        "business_name",
        first.get("business_name"),
        first.get("source_url", ""),
        _CONFIDENCE["structured"] if first.get("business_name_from_structured") else _CONFIDENCE["text"],
    )

    for result in results:
        url = result.get("source_url", "")
        take(
            "email",
            result.get("email"),
            url,
            _CONFIDENCE["structured"] if result.get("email_from_structured") else _CONFIDENCE["link"],
        )
        take("whatsapp_number", result.get("whatsapp_number"), url, _CONFIDENCE["link"])
        take("phone_number", result.get("phone_number"), url, _CONFIDENCE["labelled"])
        take(
            "address",
            result.get("address"),
            url,
            _CONFIDENCE["structured"] if result.get("address_from_structured") else _CONFIDENCE["text"],
        )
        take("contact_person", result.get("contact_person"), url, _CONFIDENCE["labelled"])
        take("business_name", result.get("business_name"), url, _CONFIDENCE["derived"])

    contact.region = detect_region(contact.address, contact.business_name)
    return contact
