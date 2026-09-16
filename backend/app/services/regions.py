"""Jakarta / Bodetabek region detection from free-text addresses."""
import re
import unicodedata
from typing import Dict, List, Optional

# Region key -> keywords that mark an address as belonging to it. Ordered most
# specific first so "Jakarta Selatan" wins over a bare "Jakarta".
REGION_KEYWORDS: Dict[str, List[str]] = {
    "jakarta_pusat": ["jakarta pusat", "jakpus", "central jakarta", "menteng", "tanah abang", "gambir", "senen", "kemayoran", "cempaka putih", "johar baru", "sawah besar"],
    "jakarta_utara": ["jakarta utara", "jakut", "north jakarta", "kelapa gading", "pluit", "penjaringan", "tanjung priok", "cilincing", "koja", "pademangan"],
    "jakarta_barat": ["jakarta barat", "jakbar", "west jakarta", "kebon jeruk", "grogol", "tambora", "cengkareng", "kalideres", "palmerah", "kembangan", "taman sari"],
    "jakarta_selatan": ["jakarta selatan", "jaksel", "south jakarta", "kebayoran", "pondok indah", "cilandak", "pasar minggu", "tebet", "mampang", "pancoran", "setiabudi", "jagakarsa", "kemang"],
    "jakarta_timur": ["jakarta timur", "jaktim", "east jakarta", "cakung", "cawang", "duren sawit", "jatinegara", "kramat jati", "pulo gadung", "makasar", "matraman", "ciracas", "cipayung", "pasar rebo"],
    "bogor": ["bogor", "cibinong", "sentul", "citeureup", "parung", "ciawi", "gunung putri", "cileungsi", "dramaga"],
    "depok": ["depok", "margonda", "cinere", "sawangan", "cimanggis", "beji", "sukmajaya", "tapos", "pancoran mas"],
    "tangerang": ["tangerang", "bsd", "serpong", "alam sutera", "ciledug", "karawaci", "cipondoh", "bintaro", "gading serpong", "pamulang", "ciputat", "curug", "balaraja"],
    "bekasi": ["bekasi", "cikarang", "harapan indah", "jatiasih", "tambun", "pondok gede", "bantar gebang", "mustika jaya", "medan satria", "babelan"],
    "jakarta": ["jakarta", "dki jakarta", "jabodetabek", "jadetabek"],
}

REGION_LABELS: Dict[str, str] = {
    "jakarta": "DKI Jakarta",
    "jakarta_pusat": "Jakarta Pusat",
    "jakarta_utara": "Jakarta Utara",
    "jakarta_barat": "Jakarta Barat",
    "jakarta_selatan": "Jakarta Selatan",
    "jakarta_timur": "Jakarta Timur",
    "bogor": "Bogor",
    "depok": "Depok",
    "tangerang": "Tangerang",
    "bekasi": "Bekasi",
    "other": "Luar Jabodetabek",
    "unknown": "Belum diketahui",
}

JABODETABEK_REGIONS = [
    "jakarta",
    "jakarta_pusat",
    "jakarta_utara",
    "jakarta_barat",
    "jakarta_selatan",
    "jakarta_timur",
    "bogor",
    "depok",
    "tangerang",
    "bekasi",
]

# Indonesian province/city names that prove the address is outside Jabodetabek.
_OUTSIDE_MARKERS = [
    "bandung", "surabaya", "semarang", "yogyakarta", "jogja", "medan", "makassar",
    "denpasar", "bali", "palembang", "malang", "solo", "surakarta", "batam",
    "balikpapan", "samarinda", "manado", "pontianak", "pekanbaru", "padang",
    "banjarmasin", "cirebon", "sukabumi", "garut", "tasikmalaya", "serang", "cilegon",
]


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    return re.sub(r"[^a-z0-9\s]+", " ", text)


def detect_region(*texts: Optional[str]) -> str:
    """Return a region key for the first Jabodetabek match found in the inputs."""
    haystack = _normalize(" ".join(t for t in texts if t))
    if not haystack.strip():
        return "unknown"

    padded = f" {haystack} "
    for region, keywords in REGION_KEYWORDS.items():
        for keyword in keywords:
            if f" {keyword} " in padded:
                return region

    for marker in _OUTSIDE_MARKERS:
        if f" {marker} " in padded:
            return "other"

    return "unknown"


def region_label(region: Optional[str]) -> str:
    if not region:
        return REGION_LABELS["unknown"]
    return REGION_LABELS.get(region, region.replace("_", " ").title())


def is_jabodetabek(region: Optional[str]) -> bool:
    return region in JABODETABEK_REGIONS
