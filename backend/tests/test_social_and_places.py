"""Social profile links, and Google Places as a second discovery provider.

Social links are read from the target's own website - the only lawful route,
since Meta, TikTok and LinkedIn all forbid scraping their platforms. Nothing
here contacts those platforms.
"""
import pytest
from bs4 import BeautifulSoup

from app.config import settings
from app.services import places
from app.services.extractor import (
    extract_from_page,
    extract_social_links,
    merge_page_results,
    social_handle,
)

pytestmark = pytest.mark.asyncio


FOOTER_HTML = """
<html><body>
  <h1>Warung Kopi Senja</h1>
  <footer>
    <a href="https://www.instagram.com/kopisenja.id/">Instagram</a>
    <a href="https://facebook.com/kopisenjajakarta">Facebook</a>
    <a href="https://www.tiktok.com/@kopisenja">TikTok</a>
    <a href="https://id.linkedin.com/company/kopi-senja">LinkedIn</a>
    <a href="https://www.youtube.com/@kopisenja">YouTube</a>
    <a href="https://shopee.co.id/kopisenja">Shopee</a>
  </footer>
</body></html>
"""

# Share buttons and platform furniture, not the business's own accounts.
NOISE_HTML = """
<html><body>
  <a href="https://www.facebook.com/sharer/sharer.php?u=https://x.co.id">Bagikan</a>
  <a href="https://twitter.com/intent/tweet?url=https://x.co.id">Tweet</a>
  <a href="https://www.instagram.com/explore/tags/kopi/">#kopi</a>
  <a href="https://www.instagram.com/p/Cxyz123/">Lihat post</a>
  <a href="/kontak">Kontak</a>
  <a href="mailto:halo@x.co.id">Email</a>
</body></html>
"""


class TestSocialLinkExtraction:
    def _links(self, html: str):
        return extract_social_links(BeautifulSoup(html, "lxml"))

    async def test_finds_every_platform_the_site_links(self):
        links = self._links(FOOTER_HTML)
        assert links["instagram"] == "https://www.instagram.com/kopisenja.id"
        assert links["facebook"] == "https://facebook.com/kopisenjajakarta"
        assert links["tiktok"] == "https://www.tiktok.com/@kopisenja"
        assert links["linkedin"] == "https://id.linkedin.com/company/kopi-senja"
        assert links["youtube"] == "https://www.youtube.com/@kopisenja"
        assert links["shopee"] == "https://shopee.co.id/kopisenja"

    async def test_ignores_share_buttons_and_platform_pages(self):
        """A share link is not the business's account."""
        links = self._links(NOISE_HTML)
        assert links == {}

    async def test_tracking_parameters_are_dropped(self):
        html = '<a href="https://www.instagram.com/kopisenja/?utm_source=web&hl=id">IG</a>'
        assert self._links(html)["instagram"] == "https://www.instagram.com/kopisenja"

    async def test_first_link_wins_per_platform(self):
        html = (
            '<a href="https://instagram.com/akun-utama">satu</a>'
            '<a href="https://instagram.com/akun-lain">dua</a>'
        )
        assert self._links(html)["instagram"] == "https://instagram.com/akun-utama"

    async def test_relative_and_non_http_links_ignored(self):
        html = '<a href="/instagram">IG</a><a href="javascript:void(0)">x</a>'
        assert self._links(html) == {}

    async def test_handle_is_readable(self):
        assert social_handle("instagram", "https://www.instagram.com/kopisenja.id") == "kopisenja.id"
        assert social_handle("tiktok", "https://www.tiktok.com/@kopisenja") == "kopisenja"
        assert social_handle("instagram", "bukan-url") is None

    async def test_page_extraction_includes_social(self):
        result = extract_from_page(FOOTER_HTML, "https://kopisenja.co.id/")
        assert result["social_links"]["instagram"].endswith("kopisenja.id")

    async def test_links_merge_across_pages(self):
        """A site often links Instagram in the footer and LinkedIn on About."""
        home = extract_from_page(
            '<html><body><a href="https://instagram.com/kopisenja">IG</a></body></html>',
            "https://kopisenja.co.id/",
        )
        about = extract_from_page(
            '<html><body><a href="https://linkedin.com/company/kopisenja">LI</a></body></html>',
            "https://kopisenja.co.id/tentang",
        )
        merged = merge_page_results([home, about])
        assert set(merged.social_links) == {"instagram", "linkedin"}

    async def test_absent_social_is_an_empty_dict_not_none(self):
        merged = merge_page_results([extract_from_page("<html><body>x</body></html>", "https://a.co.id/")])
        assert merged.social_links == {}


class TestSocialInApi:
    async def test_lead_exposes_social_links(self, auth_client, mock_db):
        from datetime import datetime, timezone

        from bson import ObjectId

        project = (
            await auth_client.post("/api/projects", json={"name": "Proyek Sosmed", "target_region": "jakarta"})
        ).json()
        me = (await auth_client.get("/api/auth/me")).json()
        lead = await mock_db.leads.insert_one(
            {
                "project_id": ObjectId(project["id"]),
                "tenant_id": ObjectId(me["tenant"]["id"]),
                "website_url": "https://kopisenja.co.id/",
                "business_name": "Warung Kopi Senja",
                "social_links": {"instagram": "https://instagram.com/kopisenja"},
                "status": "new",
                "tags": [],
                "created_at": datetime.now(timezone.utc),
            }
        )
        body = (await auth_client.get(f"/api/leads/{lead.inserted_id}")).json()
        assert body["social_links"]["instagram"].endswith("kopisenja")

    async def test_csv_export_has_social_columns(self, auth_client, mock_db):
        from datetime import datetime, timezone

        from bson import ObjectId

        project = (
            await auth_client.post("/api/projects", json={"name": "Proyek CSV", "target_region": "jakarta"})
        ).json()
        me = (await auth_client.get("/api/auth/me")).json()
        await mock_db.leads.insert_one(
            {
                "project_id": ObjectId(project["id"]),
                "tenant_id": ObjectId(me["tenant"]["id"]),
                "website_url": "https://kopisenja.co.id/",
                "business_name": "Warung Kopi Senja",
                "social_links": {
                    "instagram": "https://instagram.com/kopisenja",
                    "tiktok": "https://tiktok.com/@kopisenja",
                },
                "status": "new",
                "tags": [],
                "created_at": datetime.now(timezone.utc),
            }
        )
        csv_text = (await auth_client.get("/api/exports/leads.csv")).text
        assert "instagram" in csv_text.splitlines()[0]
        assert "https://instagram.com/kopisenja" in csv_text
        assert "https://tiktok.com/@kopisenja" in csv_text


class TestGooglePlaces:
    async def test_disabled_without_a_key(self, monkeypatch):
        monkeypatch.setattr(settings, "google_places_api_key", "")
        assert not places.is_configured()
        with pytest.raises(places.PlacesNotConfigured):
            await places.search_nearby((-6.16, 106.75, -6.08, 107.00), "kuliner")

    async def test_field_mask_stays_minimal(self):
        """Every extra field re-prices the call; ratings/hours must not creep in."""
        assert "places.websiteUri" in places.FIELD_MASK
        for costly in ("rating", "openingHours", "reviews", "photos", "priceLevel"):
            assert costly not in places.FIELD_MASK

    async def test_circle_covers_the_whole_region(self):
        bbox = (-6.16, 106.75, -6.08, 107.00)
        lat, lon, radius = places.centre_and_radius(bbox)
        assert -6.16 < lat < -6.08
        assert 106.75 < lon < 107.00
        # Must reach the corner, not just the edge midpoint.
        half_width_m = (107.00 - 106.75) / 2 * 111_000 * 0.995
        assert radius >= half_width_m
        assert radius <= places.MAX_RADIUS_M

    async def test_radius_is_capped_at_the_api_limit(self):
        _, _, radius = places.centre_and_radius((-10.0, 100.0, 0.0, 115.0))
        assert radius == places.MAX_RADIUS_M

    async def test_every_category_maps_to_google_types(self):
        from app.services.discovery import CATEGORY_FILTERS

        assert set(places.CATEGORY_TYPES) == set(CATEGORY_FILTERS)
        assert all(types for types in places.CATEGORY_TYPES.values())

    async def test_parses_a_response(self):
        payload = {
            "places": [
                {
                    "id": "abc123",
                    "displayName": {"text": "Mang Engking Kelapa Gading"},
                    "formattedAddress": "Jl. Boulevard Raya, Jakarta Utara",
                    "websiteUri": "https://www.mangengkinggroup.co.id/",
                    "nationalPhoneNumber": "(021) 1234567",
                },
                {"id": "no-site", "displayName": {"text": "Tanpa Website"}},
                {
                    "id": "dup",
                    "displayName": {"text": "Cabang Lain"},
                    "websiteUri": "https://www.mangengkinggroup.co.id",
                },
            ]
        }
        found = places.parse_places(payload, "kuliner")
        assert len(found) == 1, "tanpa website dilewati, duplikat situs digabung"
        assert found[0].name == "Mang Engking Kelapa Gading"
        assert found[0].osm_id.startswith("google/")

    async def test_unknown_category_rejected(self, monkeypatch):
        monkeypatch.setattr(settings, "google_places_api_key", "kunci-uji")
        with pytest.raises(ValueError):
            await places.search_nearby((-6.16, 106.75, -6.08, 107.00), "peternakan-naga")


class TestProviderSelection:
    async def test_google_hidden_when_not_configured(self, auth_client, monkeypatch):
        monkeypatch.setattr(settings, "google_places_api_key", "")
        body = (await auth_client.get("/api/discovery/options")).json()
        assert [p["key"] for p in body["providers"]] == ["osm"]

    async def test_google_offered_when_configured(self, auth_client, monkeypatch):
        monkeypatch.setattr(settings, "google_places_api_key", "kunci-uji")
        body = (await auth_client.get("/api/discovery/options")).json()
        assert {p["key"] for p in body["providers"]} == {"osm", "google"}

    async def test_search_uses_google_when_asked(self, auth_client, monkeypatch):
        monkeypatch.setattr(settings, "google_places_api_key", "kunci-uji")

        async def fake(bbox, category, limit=20):
            return places.parse_places(
                {"places": [{"id": "x", "displayName": {"text": "Contoh"},
                             "websiteUri": "https://contoh.co.id/"}]},
                category,
            )

        monkeypatch.setattr(places, "search_nearby", fake)
        body = (
            await auth_client.post(
                "/api/discovery/search",
                json={"region": "jakarta_utara", "category": "kuliner", "provider": "google"},
            )
        ).json()
        assert body["provider"] == "google"
        assert body["places"][0]["name"] == "Contoh"
        assert "Google" in body["attribution"]

    async def test_google_errors_are_reported_not_swallowed(self, auth_client, monkeypatch):
        monkeypatch.setattr(settings, "google_places_api_key", "kunci-uji")

        async def failing(bbox, category, limit=20):
            raise places.PlacesError("Google menolak API key (403).")

        monkeypatch.setattr(places, "search_nearby", failing)
        response = await auth_client.post(
            "/api/discovery/search",
            json={"region": "jakarta_utara", "category": "kuliner", "provider": "google"},
        )
        assert response.status_code == 502
        assert "403" in response.json()["detail"]

    async def test_unknown_provider_rejected(self, auth_client):
        response = await auth_client.post(
            "/api/discovery/search",
            json={"region": "jakarta_utara", "category": "kuliner", "provider": "bing"},
        )
        assert response.status_code == 422

    async def test_osm_remains_the_default(self, auth_client, monkeypatch):
        from app.services import discovery

        async def fake_search(region, category, limit=60):
            return discovery.DiscoveryResult()

        monkeypatch.setattr(discovery, "search", fake_search)
        body = (
            await auth_client.post(
                "/api/discovery/search", json={"region": "bogor", "category": "kuliner"}
            )
        ).json()
        assert body["provider"] == "osm"
