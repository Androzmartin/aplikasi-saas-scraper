from app.services.extractor import (
    extract_contact_person,
    extract_from_page,
    is_mobile,
    is_valid_public_email,
    merge_page_results,
    normalize_phone,
)

HOMEPAGE = """
<html><head>
  <title>Warung Kopi Senja | Beranda</title>
  <meta property="og:site_name" content="Warung Kopi Senja">
  <script type="application/ld+json">
  {"@type":"LocalBusiness","name":"Warung Kopi Senja","telephone":"021-7220091",
   "address":{"streetAddress":"Jl. Kemang Raya No. 12","addressLocality":"Jakarta Selatan","postalCode":"12730"}}
  </script>
</head><body>
  <h1>Warung Kopi Senja</h1>
  <p>Telp: 021-7220091</p>
  <a href="https://wa.me/6281234567890">Chat WhatsApp</a>
  <a href="mailto:halo@kopisenja.co.id">Email kami</a>
</body></html>
"""

CONTACT_PAGE = """
<html><body>
  <address>Jl. Kemang Raya No. 12, Jakarta Selatan 12730</address>
  <p>Contact Person: Budi Santoso</p>
  <p>WhatsApp: 0812-3456-7890</p>
</body></html>
"""


class TestPhoneNormalisation:
    def test_indonesian_formats_converge(self):
        for raw in ["0812-3456-7890", "+62 812 3456 7890", "62 812 3456 7890", "(0812) 34567890"]:
            assert normalize_phone(raw) == "+6281234567890"

    def test_landline_keeps_area_code(self):
        assert normalize_phone("021-7220091") == "+62217220091"

    def test_rejects_implausible_numbers(self):
        assert normalize_phone("123") is None
        assert normalize_phone("") is None
        assert normalize_phone("99999999999999999999") is None

    def test_mobile_detection(self):
        assert is_mobile("+6281234567890")
        assert not is_mobile("+62217220091")
        assert not is_mobile(None)


class TestEmailValidation:
    def test_accepts_real_business_email(self):
        assert is_valid_public_email("halo@kopisenja.co.id")

    def test_rejects_placeholder_and_asset_noise(self):
        for bad in ["you@example.com", "name@domain.com", "logo@2x.png", "a@sentry.io"]:
            assert not is_valid_public_email(bad)


class TestContactPerson:
    def test_reads_indonesian_and_english_labels(self):
        assert extract_contact_person("Contact Person: Budi Santoso") == "Budi Santoso"
        assert extract_contact_person("Narahubung : Ibu Siti Rahayu") == "Siti Rahayu"

    def test_ignores_prose_and_numbers(self):
        assert extract_contact_person("hubungi kami sekarang") is None
        assert extract_contact_person("PIC: 08123456") is None


class TestPageExtraction:
    def test_structured_data_drives_core_fields(self):
        result = extract_from_page(HOMEPAGE, "https://kopisenja.co.id/")
        assert result["business_name"] == "Warung Kopi Senja"
        assert result["phone_number"] == "+62217220091"
        assert result["whatsapp_number"] == "+6281234567890"
        assert result["email"] == "halo@kopisenja.co.id"
        assert "Kemang" in result["address"]

    def test_merge_prefers_homepage_name_and_fills_from_contact_page(self):
        pages = [
            extract_from_page(HOMEPAGE, "https://kopisenja.co.id/"),
            extract_from_page(CONTACT_PAGE, "https://kopisenja.co.id/kontak"),
        ]
        merged = merge_page_results(pages)
        assert merged.business_name == "Warung Kopi Senja"
        assert merged.contact_person == "Budi Santoso"
        assert merged.region == "jakarta_selatan"
        # Provenance points at the page each field actually came from.
        assert merged.field_sources["contact_person"].endswith("/kontak")
        assert merged.field_confidence["email"] > 0.5

    def test_empty_input_is_safe(self):
        assert merge_page_results([]).business_name is None
