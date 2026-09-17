"""Pencarian kata kunci dan penyaringan rating.

Kebutuhan bisnisnya: temukan usaha yang SUDAH punya website tetapi ratingnya
buruk - itulah calon klien redesign paling kuat.
"""
import pytest

from app.config import settings
from app.services import places

pytestmark = pytest.mark.asyncio

BBOX = (-6.16, 106.75, -6.08, 107.00)

PAYLOAD = {
    "places": [
        {"id": "a", "displayName": {"text": "Bengkel Bagus"},
         "websiteUri": "https://bagus.co.id/", "rating": 4.8, "userRatingCount": 210},
        {"id": "b", "displayName": {"text": "Bengkel Sedang"},
         "websiteUri": "https://sedang.co.id/", "rating": 3.9, "userRatingCount": 64},
        {"id": "c", "displayName": {"text": "Bengkel Jelek"},
         "websiteUri": "https://jelek.co.id/", "rating": 2.6, "userRatingCount": 31},
        {"id": "d", "displayName": {"text": "Bengkel Baru"},
         "websiteUri": "https://baru.co.id/"},
        {"id": "e", "displayName": {"text": "Tanpa Website"}, "rating": 1.5},
    ]
}


class TestRatingFilter:
    async def test_keeps_only_poor_performers(self):
        hasil = places.parse_places(PAYLOAD, "keyword", max_rating=3.5)
        assert [p.name for p in hasil] == ["Bengkel Jelek", "Bengkel Baru"]

    async def test_unrated_places_are_kept(self):
        """Belum ada rating bukan bukti ratingnya bagus."""
        hasil = places.parse_places(PAYLOAD, "keyword", max_rating=3.0)
        assert any(p.name == "Bengkel Baru" and p.rating is None for p in hasil)

    async def test_without_filter_everything_with_a_website_passes(self):
        hasil = places.parse_places(PAYLOAD, "keyword")
        assert len(hasil) == 4  # "Tanpa Website" tetap dibuang

    async def test_a_place_without_a_website_is_never_returned(self):
        """Tidak ada website berarti tidak ada yang bisa diaudit atau di-redesign."""
        hasil = places.parse_places(PAYLOAD, "keyword", max_rating=2.0)
        assert all(p.website for p in hasil)
        assert "Tanpa Website" not in [p.name for p in hasil]

    async def test_minimum_review_count(self):
        hasil = places.parse_places(PAYLOAD, "keyword", min_reviews=50)
        assert [p.name for p in hasil] == ["Bengkel Bagus", "Bengkel Sedang"]

    async def test_rating_and_count_are_carried_through(self):
        hasil = places.parse_places(PAYLOAD, "keyword", max_rating=3.0)
        jelek = next(p for p in hasil if p.name == "Bengkel Jelek")
        assert jelek.rating == 2.6
        assert jelek.review_count == 31

    async def test_boundary_is_inclusive(self):
        payload = {"places": [
            {"id": "x", "displayName": {"text": "Pas Batas"},
             "websiteUri": "https://pas.co.id/", "rating": 3.5},
        ]}
        assert len(places.parse_places(payload, "keyword", max_rating=3.5)) == 1


class TestTextSearch:
    async def test_requires_configuration(self, monkeypatch):
        monkeypatch.setattr(settings, "google_places_api_key", "")
        with pytest.raises(places.PlacesNotConfigured):
            await places.search_text("bengkel", BBOX)

    async def test_rejects_an_empty_keyword(self, monkeypatch):
        monkeypatch.setattr(settings, "google_places_api_key", "kunci-uji")
        with pytest.raises(ValueError):
            await places.search_text("   ", BBOX)

    async def test_field_mask_asks_for_the_rating(self):
        """Rating adalah inti mode ini; tanpa field itu penyaringan mustahil."""
        assert "places.rating" in places.TEXT_FIELD_MASK
        assert "places.userRatingCount" in places.TEXT_FIELD_MASK
        assert "nextPageToken" in places.TEXT_FIELD_MASK

    async def test_field_mask_adds_no_costlier_fields(self):
        for mahal in ("reviews", "photos", "openingHours", "priceLevel", "editorialSummary"):
            assert mahal not in places.TEXT_FIELD_MASK

    async def test_paging_is_bounded(self):
        assert places.MAX_PAGES <= 3, "lebih banyak halaman = lebih banyak tagihan"


class TestApi:
    async def test_keyword_rejected_on_openstreetmap(self, auth_client):
        """OSM tidak punya cukup nama usaha Indonesia untuk dicari begitu."""
        response = await auth_client.post(
            "/api/discovery/search",
            json={"region": "jakarta_utara", "keyword": "bengkel mobil", "provider": "osm"},
        )
        assert response.status_code == 400
        assert "Google" in response.json()["detail"]

    async def test_keyword_search_via_google(self, auth_client, monkeypatch):
        monkeypatch.setattr(settings, "google_places_api_key", "kunci-uji")
        terpakai = {}

        async def fake(query, bbox, max_rating=None, min_reviews=0, pages=3):
            terpakai.update(query=query, max_rating=max_rating)
            return places.parse_places(PAYLOAD, "keyword", max_rating=max_rating)

        monkeypatch.setattr(places, "search_text", fake)
        body = (
            await auth_client.post(
                "/api/discovery/search",
                json={
                    "region": "jakarta_utara",
                    "provider": "google",
                    "keyword": "bengkel mobil",
                    "max_rating": 3.5,
                },
            )
        ).json()

        assert terpakai["query"] == "bengkel mobil"
        assert terpakai["max_rating"] == 3.5
        assert [p["name"] for p in body["places"]] == ["Bengkel Jelek", "Bengkel Baru"]
        assert body["places"][0]["rating"] == 2.6

    async def test_category_search_still_works_without_a_keyword(self, auth_client, monkeypatch):
        monkeypatch.setattr(settings, "google_places_api_key", "kunci-uji")
        dipanggil = {}

        async def fake_nearby(bbox, category, limit=20):
            dipanggil["category"] = category
            return []

        monkeypatch.setattr(places, "search_nearby", fake_nearby)
        response = await auth_client.post(
            "/api/discovery/search",
            json={"region": "bogor", "provider": "google", "category": "kuliner"},
        )
        assert response.status_code == 200
        assert dipanggil["category"] == "kuliner"

    async def test_rating_outside_the_scale_is_rejected(self, auth_client):
        response = await auth_client.post(
            "/api/discovery/search",
            json={"region": "jakarta_utara", "provider": "google",
                  "keyword": "bengkel", "max_rating": 9},
        )
        assert response.status_code == 422
