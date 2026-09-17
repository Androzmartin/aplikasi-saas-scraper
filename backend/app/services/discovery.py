"""Find UMKM that already have a website, by area and category.

Data source is OpenStreetMap via the Overpass API. That choice is deliberate:
OSM data is openly licensed (ODbL) and Overpass explicitly permits querying, so
this does not put the product on the wrong side of anyone's terms of service.
Scraping Google Search results would; the Google Places API would need a billed
key. Attribution is required and is returned with every response.

Public Overpass instances are shared and frequently congested, so requests are
retried across mirrors and a failure is reported plainly rather than pretended
away.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.services.urls import InvalidUrlError, normalize_url

logger = logging.getLogger(__name__)

ATTRIBUTION = "Data © kontributor OpenStreetMap (ODbL)"

# Shared public instances, tried in order.
MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

REQUEST_TIMEOUT = 90.0
QUERY_TIMEOUT = 50  # seconds, given to Overpass itself
MAX_LIMIT = 200

# Approximate bounding boxes (south, west, north, east) for the target market.
REGION_BBOX: Dict[str, Tuple[float, float, float, float]] = {
    "jakarta": (-6.38, 106.68, -6.08, 107.00),
    "jakarta_pusat": (-6.22, 106.80, -6.14, 106.87),
    "jakarta_utara": (-6.16, 106.75, -6.08, 107.00),
    "jakarta_barat": (-6.22, 106.68, -6.12, 106.82),
    "jakarta_selatan": (-6.37, 106.75, -6.22, 106.85),
    "jakarta_timur": (-6.37, 106.85, -6.17, 106.99),
    "bogor": (-6.70, 106.70, -6.45, 106.90),
    "depok": (-6.47, 106.75, -6.34, 106.87),
    "tangerang": (-6.32, 106.55, -6.10, 106.76),
    "bekasi": (-6.38, 106.94, -6.14, 107.12),
}

# Category -> the OSM tag filters that identify it. Each entry is a list of
# raw filter strings appended to node/way queries.
CATEGORY_FILTERS: Dict[str, Dict[str, Any]] = {
    "kuliner": {
        "label": "Kuliner (restoran, kafe, bakery)",
        "filters": ['[amenity~"^(restaurant|cafe|fast_food|bar|food_court)$"]', '[shop=bakery]'],
    },
    "fashion": {
        "label": "Fashion & pakaian",
        "filters": ['[shop~"^(clothes|shoes|boutique|bag|jewelry|fabric|tailor)$"]'],
    },
    "kecantikan": {
        "label": "Salon & kecantikan",
        "filters": ['[shop~"^(hairdresser|beauty|cosmetics)$"]'],
    },
    "kesehatan": {
        "label": "Klinik & kesehatan",
        "filters": ['[amenity~"^(clinic|doctors|dentist|pharmacy|veterinary)$"]'],
    },
    "otomotif": {
        "label": "Otomotif & bengkel",
        "filters": ['[shop~"^(car_repair|car|motorcycle|motorcycle_repair|tyres|car_parts)$"]'],
    },
    "pendidikan": {
        "label": "Pendidikan & kursus",
        "filters": [
            '[amenity~"^(school|college|language_school|driving_school|music_school)$"]',
            '[office=educational_institution]',
        ],
    },
    "properti": {
        "label": "Properti & agen",
        "filters": ['[office~"^(estate_agent|property_management)$"]'],
    },
    "penginapan": {
        "label": "Hotel & penginapan",
        "filters": ['[tourism~"^(hotel|guest_house|hostel|apartment)$"]'],
    },
    "toko": {
        "label": "Toko & retail lainnya",
        "filters": ['[shop]'],
    },
    "jasa": {
        "label": "Jasa (laundry, percetakan, dll)",
        "filters": [
            '[shop~"^(laundry|dry_cleaning|copyshop|printing|travel_agency|florist|photo)$"]',
            '[craft]',
        ],
    },
}

# A business whose only web presence is social media has no website to audit or
# redesign - which makes it a strong prospect, so it is reported separately
# rather than silently dropped.
_SOCIAL_HOSTS = (
    "instagram.com", "facebook.com", "fb.com", "fb.me", "tiktok.com",
    "twitter.com", "x.com", "linktr.ee", "wa.me", "whatsapp.com",
    "youtube.com", "shopee.co.id", "tokopedia.com", "linkedin.com",
)


class DiscoveryError(Exception):
    """Raised when no Overpass mirror could answer."""


@dataclass
class DiscoveredPlace:
    name: str
    website: Optional[str]
    raw_website: str
    address: Optional[str]
    category: str
    lat: Optional[float]
    lon: Optional[float]
    osm_id: str
    is_social_only: bool = False
    # Only Google supplies these; OpenStreetMap has no ratings.
    rating: Optional[float] = None
    review_count: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "website": self.website,
            "raw_website": self.raw_website,
            "address": self.address,
            "category": self.category,
            "lat": self.lat,
            "lon": self.lon,
            "osm_id": self.osm_id,
            "is_social_only": self.is_social_only,
            "rating": self.rating,
            "review_count": self.review_count,
        }


@dataclass
class DiscoveryResult:
    places: List[DiscoveredPlace] = field(default_factory=list)
    social_only: List[DiscoveredPlace] = field(default_factory=list)
    attribution: str = ATTRIBUTION
    mirror_used: str = ""


def list_regions() -> List[Dict[str, str]]:
    from app.services.regions import region_label

    return [{"key": key, "label": region_label(key)} for key in REGION_BBOX]


def list_categories() -> List[Dict[str, str]]:
    return [{"key": key, "label": value["label"]} for key, value in CATEGORY_FILTERS.items()]


def build_query(region: str, category: str, limit: int) -> str:
    """Compose the Overpass QL for one area/category.

    The [website] filter is not just a convenience: it makes the query far
    cheaper, which matters on congested public instances.
    """
    if region not in REGION_BBOX:
        raise ValueError(f"Wilayah tidak dikenal: {region}")
    if category not in CATEGORY_FILTERS:
        raise ValueError(f"Kategori tidak dikenal: {category}")

    south, west, north, east = REGION_BBOX[region]
    bbox = f"{south},{west},{north},{east}"
    limit = max(1, min(limit, MAX_LIMIT))

    parts: List[str] = []
    for tag_filter in CATEGORY_FILTERS[category]["filters"]:
        for kind in ("node", "way"):
            # Both spellings are used in the wild for the website tag.
            parts.append(f'{kind}{tag_filter}["website"]({bbox});')
            parts.append(f'{kind}{tag_filter}["contact:website"]({bbox});')

    body = "\n  ".join(parts)
    return f"[out:json][timeout:{QUERY_TIMEOUT}];\n(\n  {body}\n);\nout center tags {limit};"


def _is_social_only(url: str) -> bool:
    lowered = url.lower()
    return any(host in lowered for host in _SOCIAL_HOSTS)


def _compose_address(tags: Dict[str, str]) -> Optional[str]:
    parts = [
        tags.get("addr:street"),
        tags.get("addr:housenumber"),
        tags.get("addr:suburb"),
        tags.get("addr:city"),
        tags.get("addr:postcode"),
    ]
    joined = ", ".join(str(p).strip() for p in parts if p)
    return re.sub(r"\s+", " ", joined).strip(", ") or None


def parse_elements(elements: List[Dict[str, Any]], category: str) -> DiscoveryResult:
    """Turn raw Overpass elements into places, de-duplicated by website."""
    result = DiscoveryResult()
    seen_sites: set = set()

    for element in elements:
        tags = element.get("tags") or {}
        raw_site = (tags.get("website") or tags.get("contact:website") or "").strip()
        if not raw_site:
            continue

        name = (tags.get("name") or "").strip() or "(tanpa nama)"
        address = _compose_address(tags)
        lat = element.get("lat") or (element.get("center") or {}).get("lat")
        lon = element.get("lon") or (element.get("center") or {}).get("lon")
        osm_id = f"{element.get('type', 'node')}/{element.get('id', '')}"

        if _is_social_only(raw_site):
            result.social_only.append(
                DiscoveredPlace(
                    name=name, website=None, raw_website=raw_site, address=address,
                    category=category, lat=lat, lon=lon, osm_id=osm_id, is_social_only=True,
                )
            )
            continue

        try:
            website = normalize_url(raw_site)
        except InvalidUrlError:
            continue

        key = website.rstrip("/").lower()
        if key in seen_sites:
            continue
        seen_sites.add(key)

        result.places.append(
            DiscoveredPlace(
                name=name, website=website, raw_website=raw_site, address=address,
                category=category, lat=lat, lon=lon, osm_id=osm_id,
            )
        )

    return result


async def search(region: str, category: str, limit: int = 60) -> DiscoveryResult:
    """Query Overpass for businesses with a website in the given area."""
    query = build_query(region, category, limit)
    headers = {"User-Agent": "UMKMScraperBot/1.0 (discovery; OpenStreetMap ODbL)"}
    errors: List[str] = []

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers=headers) as client:
        for mirror in MIRRORS:
            try:
                response = await client.get(mirror, params={"data": query})
            except httpx.HTTPError as exc:
                errors.append(f"{mirror}: {exc.__class__.__name__}")
                continue

            if response.status_code != 200:
                # 429/504 mean the shared instance is busy; try the next one.
                errors.append(f"{mirror}: HTTP {response.status_code}")
                await asyncio.sleep(1.0)
                continue

            try:
                payload = response.json()
            except ValueError:
                errors.append(f"{mirror}: balasan bukan JSON")
                continue

            result = parse_elements(payload.get("elements", []), category)
            result.mirror_used = mirror
            logger.info(
                "Discovery %s/%s: %s situs, %s hanya sosmed (via %s)",
                region, category, len(result.places), len(result.social_only), mirror,
            )
            return result

    raise DiscoveryError(
        "Semua server OpenStreetMap sedang sibuk. Coba lagi beberapa menit lagi. "
        f"Detail: {'; '.join(errors[:3])}"
    )
