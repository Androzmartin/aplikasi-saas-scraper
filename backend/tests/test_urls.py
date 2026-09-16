import pytest

from app.services.urls import InvalidUrlError, normalize_url, parse_url_list, same_site


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("toko.co.id", "https://toko.co.id/"),
        ("http://toko.co.id", "http://toko.co.id/"),
        ("HTTPS://Toko.CO.ID/Kontak", "https://toko.co.id/Kontak"),
        ("  https://toko.co.id/a?b=1#frag  ", "https://toko.co.id/a?b=1"),
        ("<https://toko.co.id>", "https://toko.co.id/"),
    ],
)
def test_normalize_valid_urls(raw, expected):
    assert normalize_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "ftp://toko.co.id",
        "javascript:alert(1)",
        "localhost",
        "http://127.0.0.1/admin",
        "http://192.168.1.1",
        "http://10.0.0.5:8080",
        "http://[::1]/",
        "notadomain",
    ],
)
def test_normalize_rejects_bad_and_internal_urls(raw):
    with pytest.raises(InvalidUrlError):
        normalize_url(raw)


def test_parse_url_list_dedupes_and_reports_rejections():
    accepted, rejected = parse_url_list(
        ["toko.co.id", "https://toko.co.id/", "ftp://x.com", "warung.id", ""]
    )
    assert accepted == ["https://toko.co.id/", "https://warung.id/"]
    reasons = {item["url"]: item["reason"] for item in rejected}
    assert "ftp://x.com" in reasons
    assert "Duplikat" in reasons["https://toko.co.id/"]


def test_same_site_handles_www_prefix():
    assert same_site("https://www.toko.co.id/a", "https://toko.co.id/b")
    assert not same_site("https://toko.co.id", "https://lain.co.id")
