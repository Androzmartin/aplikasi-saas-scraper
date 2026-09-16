from app.services.audit import MAX_PER_PARAMETER, run_audit

LEGACY = """
<html><body>
<table width="960px"><tr><td><font color="red"><marquee>Toko Jaya</marquee></font></td></tr></table>
</body></html>
"""

MODERN = """
<html><head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>@media (min-width: 640px) { .a { display: flex } }</style>
</head><body>
  <header><nav><a href="#a">Tentang</a><a href="#b">Layanan</a><a href="#c">Kontak</a></nav></header>
  <main>
    <h1>Toko Jaya</h1>
    <section><p>%s</p><img src="p.jpg" alt="produk">
      <a class="btn" href="https://wa.me/628123456789">Hubungi Kami</a></section>
    <section>Testimoni pelanggan kami</section>
  </main>
  <footer>Kontak: Jakarta</footer>
</body></html>
""" % ("Kami melayani kebutuhan pelanggan dengan produk berkualitas. " * 20)

FULL_CONTACT = {
    "business_name": "Toko Jaya",
    "whatsapp_number": "+628123456789",
    "phone_number": "+62211234567",
    "email": "halo@tokojaya.co.id",
    "address": "Jl. Sudirman No 1, Jakarta Pusat",
}


def test_legacy_site_scores_poorly_and_lists_issues():
    result = run_audit(LEGACY, {})
    assert result["score"] < 25
    assert result["grade"] in ("D", "E")
    assert any(issue["code"] == "no_viewport" for issue in result["issues"])
    assert any(issue["code"] == "legacy_markup" for issue in result["issues"])
    assert any(issue["code"] == "no_whatsapp" for issue in result["issues"])


def test_modern_site_scores_well():
    result = run_audit(MODERN, FULL_CONTACT)
    assert result["score"] >= 75
    assert result["grade"] in ("A", "B")
    assert result["strengths"]


def test_score_is_bounded_and_breakdown_consistent():
    for html, contact in ((LEGACY, {}), (MODERN, FULL_CONTACT), ("", {})):
        result = run_audit(html, contact)
        assert 0 <= result["score"] <= 100
        assert sum(result["breakdown"].values()) == result["score"]
        assert all(0 <= v <= MAX_PER_PARAMETER for v in result["breakdown"].values())


def test_issues_sorted_by_severity():
    issues = run_audit(LEGACY, {})["issues"]
    rank = {"high": 0, "medium": 1, "low": 2}
    severities = [rank[issue["severity"]] for issue in issues]
    assert severities == sorted(severities)


def test_summaries_are_populated():
    result = run_audit(LEGACY, {"business_name": "Toko Jaya"})
    assert "Toko Jaya" in result["opportunity_summary"]
    assert result["redesign_summary"]


def test_empty_html_does_not_crash():
    assert run_audit("", {})["score"] >= 0
