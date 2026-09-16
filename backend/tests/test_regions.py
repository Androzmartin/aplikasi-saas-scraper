import pytest

from app.services.regions import detect_region, is_jabodetabek, region_label


@pytest.mark.parametrize(
    "address,expected",
    [
        ("Jl. Kemang Raya No 5, Jakarta Selatan 12730", "jakarta_selatan"),
        ("Ruko Sentul City Blok A, Bogor", "bogor"),
        ("Jl. Margonda Raya, Depok", "depok"),
        ("BSD City, Tangerang Selatan", "tangerang"),
        ("Harapan Indah, Bekasi", "bekasi"),
        ("Menteng, Jakarta Pusat", "jakarta_pusat"),
        ("Kantor pusat di DKI Jakarta", "jakarta"),
    ],
)
def test_detects_jabodetabek_areas(address, expected):
    assert detect_region(address) == expected


def test_specific_area_wins_over_generic_jakarta():
    assert detect_region("Jakarta Selatan, DKI Jakarta") == "jakarta_selatan"


def test_marks_other_cities_and_unknown():
    assert detect_region("Jl. Braga No 1, Bandung") == "other"
    assert detect_region("") == "unknown"
    assert detect_region(None) == "unknown"


def test_accent_and_punctuation_insensitive():
    assert detect_region("JAKARTA-SELATAN!!") == "jakarta_selatan"


def test_jabodetabek_membership_and_labels():
    assert is_jabodetabek("depok")
    assert not is_jabodetabek("other")
    assert region_label("jakarta_barat") == "Jakarta Barat"
    assert region_label(None) == "Belum diketahui"
