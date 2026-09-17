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
    social_links: Dict[str, str] = field(default_factory=dict)
    images: Dict[str, Any] = field(default_factory=lambda: {"logo": None, "gallery": []})
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
            "social_links": self.social_links,
            "images": self.images,
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


# Social profiles the business linked from its own website. This is the only
# lawful way to collect these: the business published the links itself, on its
# own server, and we read them while crawling a page we are already allowed to
# fetch. Nothing is requested from Instagram, Meta, TikTok or LinkedIn - all of
# which forbid scraping in their terms.
_SOCIAL_PATTERNS: Dict[str, re.Pattern] = {
    "instagram": re.compile(r"^https?://(?:www\.)?instagram\.com/([A-Za-z0-9._]+)", re.I),
    "facebook": re.compile(r"^https?://(?:www\.|web\.|m\.)?facebook\.com/([A-Za-z0-9.\-]+)", re.I),
    "tiktok": re.compile(r"^https?://(?:www\.)?tiktok\.com/@([A-Za-z0-9._]+)", re.I),
    "linkedin": re.compile(r"^https?://(?:[a-z]{2}\.)?linkedin\.com/(?:company|in)/([A-Za-z0-9._\-]+)", re.I),
    "youtube": re.compile(r"^https?://(?:www\.)?youtube\.com/(?:@|c/|channel/|user/)([A-Za-z0-9._\-]+)", re.I),
    "twitter": re.compile(r"^https?://(?:www\.)?(?:twitter|x)\.com/([A-Za-z0-9_]+)", re.I),
    "tokopedia": re.compile(r"^https?://(?:www\.)?tokopedia\.com/([A-Za-z0-9._\-]+)", re.I),
    "shopee": re.compile(r"^https?://(?:www\.)?shopee\.co\.id/([A-Za-z0-9._\-]+)", re.I),
}

# Paths that are the platform's own furniture, not a business account.
_SOCIAL_NOISE = {
    "sharer", "share", "share.php", "home", "login", "signup", "explore",
    "privacy", "policy", "terms", "help", "about", "pages", "profile.php",
    "intent", "hashtag", "p", "reel", "reels", "tv", "watch", "groups",
    "plugins", "dialog", "tr", "events", "posts", "photo", "video",
}


def extract_social_links(soup: BeautifulSoup) -> Dict[str, str]:
    """Collect social profile URLs the site links to, one per platform.

    The first match wins: sites usually link their own profile in the header or
    footer before any share buttons appear.
    """
    found: Dict[str, str] = {}

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href.lower().startswith("http"):
            continue

        for platform, pattern in _SOCIAL_PATTERNS.items():
            if platform in found:
                continue
            match = pattern.match(href)
            if not match:
                continue
            handle = match.group(1).strip("/").lower()
            if not handle or handle in _SOCIAL_NOISE:
                continue
            # Drop tracking parameters; the profile URL is the useful part.
            found[platform] = href.split("?")[0].rstrip("/")

    return found


def social_handle(platform: str, url: str) -> Optional[str]:
    """The account name on its own, for display next to the link."""
    pattern = _SOCIAL_PATTERNS.get(platform)
    if not pattern or not url:
        return None
    match = pattern.match(url)
    return match.group(1).strip("/") if match else None


# --------------------------------------------------------------------- images

# Filenames that mark decoration or tracking rather than content.
_IMAGE_JUNK = (
    "sprite", "icon", "favicon", "pixel", "spacer", "blank", "placeholder",
    "loader", "loading", "arrow", "bullet", "divider", "pattern", "badge",
    "whatsapp", "facebook", "instagram", "tiktok", "youtube", "twitter",
    "payment", "visa", "mastercard", "gopay", "ovo", "dana", "shopee",
    "1x1", "transparent", "avatar", "captcha",
)

# Filenames that suggest a large, presentable photo.
_IMAGE_GOOD = (
    "banner", "slide", "hero", "cover", "header", "featured", "gallery",
    "menu", "product", "produk", "foto", "photo", "interior", "room",
    "outlet", "store", "toko", "showcase", "portfolio",
)

_IMAGE_EXT_OK = (".jpg", ".jpeg", ".png", ".webp", ".avif")


def _image_candidates(tag: Any) -> str:
    """The best URL on an <img>, allowing for lazy-loading attributes."""
    for attr in ("src", "data-src", "data-lazy-src", "data-original"):
        value = (tag.get(attr) or "").strip()
        if value and not value.startswith("data:"):
            return value

    # srcset: take the last (usually largest) entry.
    srcset = (tag.get("srcset") or tag.get("data-srcset") or "").strip()
    if srcset:
        last = srcset.split(",")[-1].strip().split(" ")[0]
        if last and not last.startswith("data:"):
            return last
    return ""


# Many CMSs encode the rendered size in the filename - "cover_w480_h288",
# "photo-1024x768". Reading it avoids picking a thumbnail for a full-bleed hero,
# which looks blurry however good the photo is.
_DIM_IN_NAME = [
    re.compile(r"[_-]w(\d{2,4})[_-]h\d{2,4}", re.I),
    re.compile(r"[_-](\d{3,4})x\d{3,4}\.", re.I),
]


def width_from_url(url: str) -> int:
    for pattern in _DIM_IN_NAME:
        match = pattern.search(url)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                continue
    return 0


def _score_image(url: str, tag: Any) -> int:
    """Rank how likely an image is to be a usable photo of the business."""
    lowered = url.lower()
    score = 0

    try:
        width = int(str(tag.get("width") or "").strip() or 0)
    except ValueError:
        width = 0
    # The attribute is often missing; the filename usually is not.
    width = max(width, width_from_url(url))
    if width >= 1200:
        score += 6
    elif width >= 800:
        score += 4
    elif width >= 400:
        score += 2
    elif 0 < width < 200:
        score -= 6  # too small to be a photo

    score += sum(3 for hint in _IMAGE_GOOD if hint in lowered)

    # A written alt usually means real content, not furniture.
    alt = (tag.get("alt") or "").strip()
    if len(alt) > 8:
        score += 2

    # Thumbnail markers in the path.
    if "thumb" in lowered or "-150x" in lowered or "-300x" in lowered:
        score -= 2
    return score


def extract_images(soup: BeautifulSoup, base_url: str) -> Dict[str, Any]:
    """Collect the business's own logo and photos from its page.

    These are used to build the redesign concept, which is a mockup made *for*
    that business out of its own material - not a generic stock page.
    """
    from urllib.parse import urljoin

    logo: Optional[str] = None
    scored: List[Tuple[int, str]] = []
    seen: set = set()

    # og:image is the site's own pick for how it wants to be represented.
    og_image = soup.find("meta", attrs={"property": "og:image"})
    if og_image and (og_image.get("content") or "").strip():
        candidate = urljoin(base_url, og_image["content"].strip())
        if not candidate.startswith("data:"):
            scored.append((12, candidate))
            seen.add(candidate)

    for tag in soup.find_all("img"):
        raw = _image_candidates(tag)
        if not raw:
            continue
        url = urljoin(base_url, raw)
        lowered = url.lower()

        if url in seen or lowered.startswith("data:"):
            continue
        if not any(lowered.split("?")[0].endswith(ext) for ext in _IMAGE_EXT_OK):
            continue

        haystack = f"{lowered} {(tag.get('alt') or '').lower()} {(tag.get('class') or '')}"
        if any(junk in haystack for junk in _IMAGE_JUNK):
            # A logo is junk for the gallery but wanted on its own.
            if "logo" in haystack and logo is None:
                logo = url
            continue
        if "logo" in haystack:
            if logo is None:
                logo = url
            continue

        seen.add(url)
        scored.append((_score_image(url, tag), url))

    scored.sort(key=lambda item: -item[0])
    gallery = [url for score, url in scored if score > 0][:8]

    return {"logo": logo, "gallery": gallery}


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
        "social_links": extract_social_links(soup),
        "images": extract_images(soup, url),
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

        # Merged across pages rather than taken from one: a site often links
        # Instagram in the footer and LinkedIn only on the About page.
        for platform, link in (result.get("social_links") or {}).items():
            contact.social_links.setdefault(platform, link)

        # Photos accumulate across pages; the homepage usually scores highest,
        # but a gallery or menu page often has the better shots.
        page_images = result.get("images") or {}
        if page_images.get("logo") and not contact.images.get("logo"):
            contact.images["logo"] = page_images["logo"]
        for src in page_images.get("gallery") or []:
            if src not in contact.images["gallery"] and len(contact.images["gallery"]) < 10:
                contact.images["gallery"].append(src)

    contact.region = detect_region(contact.address, contact.business_name)
    return contact
