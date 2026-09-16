import pytest

from app.routers.exports import _csv_safe
from app.services.scraper import pick_internal_links
from app.services.storage import LocalStorage


class TestLocalStorage:
    def test_round_trip(self, tmp_path):
        store = LocalStorage(str(tmp_path))
        store.put_text("redesign/abc/v1/index.html", "<html>hi</html>")
        assert store.get_text("redesign/abc/v1/index.html") == "<html>hi</html>"

    def test_missing_key_returns_none(self, tmp_path):
        assert LocalStorage(str(tmp_path)).get_text("redesign/none/v1/index.html") is None

    @pytest.mark.parametrize("key", ["../escape.html", "a/../../escape.html", "", "a/b;rm -rf"])
    def test_rejects_traversal_and_unsafe_keys(self, tmp_path, key):
        with pytest.raises(ValueError):
            LocalStorage(str(tmp_path)).put_text(key, "x")

    def test_delete_is_idempotent(self, tmp_path):
        store = LocalStorage(str(tmp_path))
        store.put_text("a/b.html", "x")
        store.delete("a/b.html")
        store.delete("a/b.html")
        assert store.get_text("a/b.html") is None


class TestCsvSafety:
    @pytest.mark.parametrize("value", ["=cmd|'/c calc'!A1", "+1+1", "-2+3", "@SUM(A1)"])
    def test_formula_prefixes_are_neutralised(self, value):
        assert _csv_safe(value).startswith("'")

    def test_ordinary_values_untouched(self):
        assert _csv_safe("Warung Kopi") == "Warung Kopi"
        assert _csv_safe("+6281234567890").startswith("'")  # leading + is still a formula risk
        assert _csv_safe(None) == ""
        assert _csv_safe(72) == "72"


class TestCrawlScope:
    def test_only_same_site_priority_pages_are_followed(self):
        html = (
            '<a href="/kontak">Kontak</a>'
            '<a href="/tentang-kami">Tentang</a>'
            '<a href="/blog/post">Blog</a>'
            '<a href="https://lain.co.id/kontak">Eksternal</a>'
            '<a href="/brosur.pdf">Kontak PDF</a>'
        )
        links = pick_internal_links(html, "https://toko.co.id/", 5)
        assert links == ["https://toko.co.id/kontak", "https://toko.co.id/tentang-kami"]

    def test_respects_the_limit(self):
        html = "".join(f'<a href="/kontak-{i}">Kontak {i}</a>' for i in range(10))
        assert len(pick_internal_links(html, "https://toko.co.id/", 3)) == 3
