"""Google Places API (New) as a second discovery provider.

Optional, and off unless an API key is configured. Coverage in Indonesia is far
better than OpenStreetMap, but unlike OSM it is a paid, licensed service - so it
is opt-in and the caller pays.

Cost note that drives the design here: the billing tier is set by the field mask,
not by a setting. websiteUri and nationalPhoneNumber are Enterprise-tier fields,
and asking for any Enterprise field re-prices the whole call. We need the website
(that is the entire point), so every call lands at Enterprise. The mask is
therefore kept to exactly the five fields we use and nothing else - adding
ratings or opening hours would push it to Enterprise+Atmosphere for no benefit.

Billing is per request, not per place: one request returns up to 20 businesses.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import settings
from app.services.urls import InvalidUrlError, normalize_url

logger = logging.getLogger(__name__)

ENDPOINT = "https://places.googleapis.com/v1/places:searchNearby"
ATTRIBUTION = "Data tempat © Google"

# Exactly what the lead pipeline consumes. Every extra field costs money.
FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.websiteUri",
        "places.nationalPhoneNumber",
    ]
)

MAX_RESULTS_PER_CALL = 20  # hard API limit
MAX_RADIUS_M = 50_000.0    # hard API limit

# Our categories mapped to Google place types.
CATEGORY_TYPES: Dict[str, List[str]] = {
    "kuliner": ["restaurant", "cafe", "bakery", "meal_takeaway"],
    "fashion": ["clothing_store", "shoe_store", "jewelry_store"],
    "kecantikan": ["beauty_salon", "hair_care", "spa"],
    "kesehatan": ["doctor", "dentist", "pharmacy", "physiotherapist"],
    "otomotif": ["car_repair", "car_dealer", "car_wash"],
    "pendidikan": ["school", "primary_school", "secondary_school"],
    "properti": ["real_estate_agency"],
    "penginapan": ["hotel", "lodging", "guest_house"],
    "toko": ["store", "supermarket", "convenience_store"],
    "jasa": ["laundry", "florist", "travel_agency", "moving_company"],
}


class PlacesError(Exception):
    """Raised when Google rejects the request or is unreachable."""


class PlacesNotConfigured(PlacesError):
    """Raised when no API key is set."""


def is_configured() -> bool:
    return bool(settings.google_places_api_key)


def centre_and_radius(bbox: Tuple[float, float, float, float]) -> Tuple[float, float, float]:
    """Turn a bounding box into the circle the API expects.

    The radius covers the box's corner, so the circle contains the whole area
    rather than clipping it, and is capped at the API maximum.
    """
    south, west, north, east = bbox
    lat = (south + north) / 2
    lon = (west + east) / 2

    # Rough metres per degree is good enough to size a search circle.
    half_height_m = abs(north - south) / 2 * 111_000
    half_width_m = abs(east - west) / 2 * 111_000 * 0.995  # cos(~6 deg) ~ 0.995
    radius = (half_height_m**2 + half_width_m**2) ** 0.5
    return lat, lon, min(radius, MAX_RADIUS_M)


def parse_places(payload: Dict[str, Any], category: str) -> List[Any]:
    """Map the Google response onto the same shape the OSM provider returns."""
    from app.services.discovery import DiscoveredPlace

    places: List[DiscoveredPlace] = []
    seen: set = set()

    for item in payload.get("places", []) or []:
        raw_site = (item.get("websiteUri") or "").strip()
        if not raw_site:
            # Without a website there is nothing to audit or redesign.
            continue
        try:
            website = normalize_url(raw_site)
        except InvalidUrlError:
            continue

        key = website.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)

        name = ((item.get("displayName") or {}).get("text") or "").strip() or "(tanpa nama)"
        places.append(
            DiscoveredPlace(
                name=name,
                website=website,
                raw_website=raw_site,
                address=(item.get("formattedAddress") or "").strip() or None,
                category=category,
                lat=None,
                lon=None,
                osm_id=f"google/{item.get('id', '')}",
                is_social_only=False,
            )
        )

    return places


async def search_nearby(
    bbox: Tuple[float, float, float, float], category: str, limit: int = MAX_RESULTS_PER_CALL
) -> List[Any]:
    """One Nearby Search call. Returns up to 20 businesses that have a website."""
    if not is_configured():
        raise PlacesNotConfigured(
            "Google Places belum dikonfigurasi. Isi GOOGLE_PLACES_API_KEY pada server."
        )
    if category not in CATEGORY_TYPES:
        raise ValueError(f"Kategori tidak dikenal: {category}")

    lat, lon, radius = centre_and_radius(bbox)
    body = {
        "includedTypes": CATEGORY_TYPES[category],
        "maxResultCount": max(1, min(limit, MAX_RESULTS_PER_CALL)),
        "locationRestriction": {
            "circle": {"center": {"latitude": lat, "longitude": lon}, "radius": radius}
        },
        "languageCode": "id",
        "regionCode": "ID",
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.google_places_api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.google_places_timeout_seconds) as client:
            response = await client.post(ENDPOINT, json=body, headers=headers)
    except httpx.HTTPError as exc:
        raise PlacesError(f"Tidak bisa menghubungi Google Places: {exc.__class__.__name__}") from exc

    if response.status_code == 403:
        raise PlacesError(
            "Google menolak API key (403). Pastikan Places API (New) sudah diaktifkan, "
            "billing aktif, dan pembatasan key mengizinkan server ini."
        )
    if response.status_code == 429:
        raise PlacesError("Kuota Google Places habis untuk saat ini (429).")
    if response.status_code >= 400:
        detail = ""
        try:
            detail = (response.json().get("error") or {}).get("message", "")
        except ValueError:
            detail = response.text[:200]
        raise PlacesError(f"Google Places menolak permintaan (HTTP {response.status_code}): {detail}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise PlacesError("Balasan Google Places bukan JSON yang valid") from exc

    places = parse_places(payload, category)
    logger.info("Google Places %s: %s tempat dengan website", category, len(places))
    return places
