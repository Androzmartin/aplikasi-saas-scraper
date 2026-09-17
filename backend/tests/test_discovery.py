"""Discovery: finding businesses by area and category via OpenStreetMap.

The network call itself is stubbed; what is tested is the query we build, how
raw OSM elements are interpreted, and the import path into a project.
"""
import pytest

from app.services import discovery

pytestmark = pytest.mark.asyncio


SAMPLE_ELEMENTS = [
    {
        "type": "node", "id": 1, "lat": -6.15, "lon": 106.90,
        "tags": {
            "name": "Mang Engking Kelapa Gading",
            "website": "https://www.mangengkinggroup.co.id/",
            "amenity": "restaurant",
            "addr:street": "Jl. Boulevard Raya", "addr:city": "Jakarta Utara",
        },
    },
    {
        "type": "way", "id": 2, "center": {"lat": -6.14, "lon": 106.91},
        "tags": {"name": "Bakmi GM", "contact:website": "https://www.bakmigm.com/"},
    },
    # Same site as the first entry: a duplicate branch must not become a
    # second lead.
    {
        "type": "node", "id": 3,
        "tags": {"name": "Mang Engking Cabang Lain",
                 "website": "https://www.mangengkinggroup.co.id"},
    },
    # Instagram only - no website to audit, but a strong prospect.
    {
        "type": "node", "id": 4,
        "tags": {"name": "Sudo Brew", "website": "www.instagram.com/sudobrew.indonesia/"},
    },
    {"type": "node", "id": 5, "tags": {"name": "Tanpa Website", "amenity": "cafe"}},
    {"type": "node", "id": 6, "tags": {"name": "URL Rusak", "website": "bukan url sama sekali"}},
]


class TestOptions:
    async def test_regions_cover_the_target_market(self):
        keys = {r["key"] for r in discovery.list_regions()}
        assert "jakarta_utara" in keys
        assert {"bogor", "depok", "tangerang", "bekasi"} <= keys

    async def test_every_region_has_a_readable_label(self):
        assert all(r["label"] and r["label"] != r["key"] for r in discovery.list_regions())

    async def test_categories_include_the_obvious_umkm_types(self):
        keys = {c["key"] for c in discovery.list_categories()}
        assert {"kuliner", "fashion", "otomotif", "kesehatan"} <= keys

    async def test_bboxes_are_the_right_way_round(self):
        """south < north and west < east, or Overpass returns nothing."""
        for key, (south, west, north, east) in discovery.REGION_BBOX.items():
            assert south < north, key
            assert west < east, key
            # Jabodetabek sits south of the equator, east of Sumatra.
            assert -7.0 < south < -6.0, key
            assert 106.0 < west < 108.0, key


class TestQueryBuilding:
    async def test_query_has_the_pieces_overpass_needs(self):
        q = discovery.build_query("jakarta_utara", "kuliner", 40)
        assert "[out:json]" in q
        assert "out center tags 40;" in q
        assert "-6.16,106.75,-6.08,107.0" in q.replace(" ", "")

    async def test_query_filters_on_website_to_stay_cheap(self):
        """Without this filter the shared Overpass instances time out."""
        q = discovery.build_query("jakarta_utara", "kuliner", 10)
        assert '["website"]' in q
        assert '["contact:website"]' in q

    async def test_query_covers_nodes_and_ways(self):
        q = discovery.build_query("depok", "toko", 10)
        assert "node[" in q and "way[" in q

    async def test_limit_is_clamped(self):
        assert "out center tags 200;" in discovery.build_query("bogor", "kuliner", 9999)
        assert "out center tags 1;" in discovery.build_query("bogor", "kuliner", 0)

    async def test_unknown_inputs_rejected(self):
        with pytest.raises(ValueError):
            discovery.build_query("mars", "kuliner", 10)
        with pytest.raises(ValueError):
            discovery.build_query("bogor", "peternakan-naga", 10)


class TestParsing:
    async def test_extracts_usable_places(self):
        result = discovery.parse_elements(SAMPLE_ELEMENTS, "kuliner")
        names = [p.name for p in result.places]
        assert "Mang Engking Kelapa Gading" in names
        assert "Bakmi GM" in names

    async def test_reads_both_website_tag_spellings(self):
        result = discovery.parse_elements(SAMPLE_ELEMENTS, "kuliner")
        sites = {p.website for p in result.places}
        assert "https://www.bakmigm.com/" in sites  # contact:website

    async def test_same_website_is_not_returned_twice(self):
        result = discovery.parse_elements(SAMPLE_ELEMENTS, "kuliner")
        sites = [p.website for p in result.places]
        assert len(sites) == len(set(sites))

    async def test_social_only_is_separated_not_dropped(self):
        """No website means nothing to audit - but it is a strong prospect."""
        result = discovery.parse_elements(SAMPLE_ELEMENTS, "kuliner")
        assert [p.name for p in result.social_only] == ["Sudo Brew"]
        assert result.social_only[0].website is None
        assert result.social_only[0].is_social_only is True

    async def test_entries_without_a_website_are_ignored(self):
        result = discovery.parse_elements(SAMPLE_ELEMENTS, "kuliner")
        assert "Tanpa Website" not in [p.name for p in result.places]

    async def test_unusable_urls_are_dropped(self):
        result = discovery.parse_elements(SAMPLE_ELEMENTS, "kuliner")
        assert "URL Rusak" not in [p.name for p in result.places]

    async def test_address_and_coordinates_survive(self):
        result = discovery.parse_elements(SAMPLE_ELEMENTS, "kuliner")
        place = next(p for p in result.places if p.name.startswith("Mang Engking"))
        assert "Jl. Boulevard Raya" in place.address
        assert place.lat == -6.15
        assert place.osm_id == "node/1"

    async def test_way_centre_is_used_for_coordinates(self):
        result = discovery.parse_elements(SAMPLE_ELEMENTS, "kuliner")
        place = next(p for p in result.places if p.name == "Bakmi GM")
        assert place.lat == -6.14 and place.lon == 106.91

    async def test_empty_input_is_safe(self):
        result = discovery.parse_elements([], "kuliner")
        assert result.places == [] and result.social_only == []


class TestApi:
    async def test_options_endpoint(self, auth_client):
        body = (await auth_client.get("/api/discovery/options")).json()
        assert body["regions"] and body["categories"]
        # OSM's licence requires attribution wherever the data is shown.
        assert "OpenStreetMap" in body["attribution"]

    async def test_search_returns_candidates(self, auth_client, monkeypatch):
        async def fake_search(region, category, limit=60):
            return discovery.parse_elements(SAMPLE_ELEMENTS, category)

        monkeypatch.setattr(discovery, "search", fake_search)
        response = await auth_client.post(
            "/api/discovery/search", json={"region": "jakarta_utara", "category": "kuliner"}
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["places"]) == 2
        assert len(body["social_only"]) == 1
        assert "OpenStreetMap" in body["attribution"]

    async def test_search_reports_upstream_outage_honestly(self, auth_client, monkeypatch):
        async def failing(region, category, limit=60):
            raise discovery.DiscoveryError("Semua server OpenStreetMap sedang sibuk.")

        monkeypatch.setattr(discovery, "search", failing)
        response = await auth_client.post(
            "/api/discovery/search", json={"region": "jakarta_utara", "category": "kuliner"}
        )
        # Not an empty list, which would read as "no businesses here".
        assert response.status_code == 503
        assert "sibuk" in response.json()["detail"]

    async def test_bad_region_is_rejected(self, auth_client, monkeypatch):
        async def raising(region, category, limit=60):
            raise ValueError("Wilayah tidak dikenal: mars")

        monkeypatch.setattr(discovery, "search", raising)
        response = await auth_client.post(
            "/api/discovery/search", json={"region": "mars", "category": "kuliner"}
        )
        assert response.status_code == 400

    async def test_import_queues_jobs(self, auth_client):
        project = (
            await auth_client.post(
                "/api/projects", json={"name": "Proyek Discovery", "target_region": "jakarta_utara"}
            )
        ).json()
        response = await auth_client.post(
            "/api/discovery/import",
            json={
                "project_id": project["id"],
                "urls": ["https://www.mangengkinggroup.co.id/", "https://www.bakmigm.com/"],
            },
        )
        assert response.status_code == 201
        assert len(response.json()["created"]) == 2

    async def test_importing_the_same_places_twice_is_skipped(self, auth_client):
        project = (
            await auth_client.post(
                "/api/projects", json={"name": "Proyek Ulang", "target_region": "jakarta_utara"}
            )
        ).json()
        payload = {"project_id": project["id"], "urls": ["https://www.bakmigm.com/"]}
        assert len((await auth_client.post("/api/discovery/import", json=payload)).json()["created"]) == 1

        second = (await auth_client.post("/api/discovery/import", json=payload)).json()
        assert second["created"] == []
        assert "Sudah pernah diproses" in second["rejected"][0]["reason"]

    async def test_import_marks_where_the_url_came_from(self, auth_client, mock_db):
        project = (
            await auth_client.post(
                "/api/projects", json={"name": "Proyek Asal", "target_region": "bogor"}
            )
        ).json()
        await auth_client.post(
            "/api/discovery/import",
            json={"project_id": project["id"], "urls": ["https://contoh-discovery.co.id/"]},
        )
        job = await mock_db.scrape_jobs.find_one({"source_url": "https://contoh-discovery.co.id/"})
        assert job["discovered_via"] == "openstreetmap"

    async def test_cannot_import_into_another_tenants_project(self, auth_client, client):
        project = (
            await auth_client.post(
                "/api/projects", json={"name": "Milik A", "target_region": "jakarta"}
            )
        ).json()
        other = await client.post(
            "/api/auth/register",
            json={"company_name": "Agency Lain", "name": "Cici",
                  "email": "cici-disc@lain.co.id", "password": "password-lain-123"},
        )
        token = other.json()["access_token"]
        response = await client.post(
            "/api/discovery/import",
            json={"project_id": project["id"], "urls": ["https://x.co.id/"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404
