"""External news ingestion for temporary assistant-driven pings."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from urllib.parse import quote_plus, urljoin


DEFAULT_CENTER = {"lat": 8.983333, "lng": -79.516667, "label": "Panama, Panama"}
DEFAULT_LOCATION_LABEL = DEFAULT_CENTER["label"]
GENERIC_LOCATION_LABELS = {
    "panama, panama",
    "ciudad de panama",
    "panama",
    "capital",
}
METRO_BROAD_LOCATION_LABELS = {
    "san miguelito",
    "tocumen",
    "pacora",
    "chilibre",
    "panama oeste",
    "panama norte",
    "panama este",
    "ciudad de panama",
}

IRRELEVANT_KEYWORDS = (
    "economia", "pib", "bolsa", "farandula", "entretenimiento", "cultura",
    "aves", "animal", "fauna", "deporte", "futbol", "beisbol", "festival",
    "moda", "opinion", "editorial", "espectaculo", "turismo",
)
LOW_SIGNAL_NEWS = (
    "como protegerse", "como evitar", "recomendaciones", "consejos",
    "analisis", "opinion", "subsidio", "tope semanal", "mas ingresos",
    "cuestiona protesta", "impacto economico", "economia del pais",
    "del pais", "nacional", "nacionales", "a nivel nacional",
)
LOCATION_HINTS = (
    "en ", "de ", "desde ", "hacia ", "sobre ", "via ", "via ", "puente",
    "corredor", "avenida", "calle", "autopista", "mercado", "barrio",
    "sector", "provincia", "distrito", "capital",
)
STREET_LEVEL_HINTS = (
    "calle", "avenida", "ave.", "av.", "via ", "vía ", "corredor",
    "puente", "mercado", "hospital", "estacion", "estación", "metro",
    "entrada de", "salida de", "frente a", "cerca de",
)
OPERATIONAL_IMPACT_TERMS = (
    "cerrada", "cerrado", "cierre", "desvio", "desvio", "evacuar", "evacuacion",
    "aprehendidos", "aprehendido", "operativo", "suspendido", "suspendida",
    "afecta", "afectados", "interrumpido", "interrumpida", "sin paso",
    "congestion", "trafico", "desabastecimiento", "sin servicio", "bloqueo",
)
SERVICE_ALERT_TERMS = (
    "gasolina", "combustible", "medicamento", "farmacia", "hospital",
    "clinica", "desabastecimiento", "escasez",
)

CATEGORY_RULES = [
    ("Aviso ciudadano", ("gasolina", "combustible", "medicamento", "farmacia", "hospital", "clinica", "desabastecimiento", "escasez")),
    ("Incendio", ("incendio", "fuego", "humo")),
    ("Inundacion", ("inundacion", "lluvia", "desbordamiento")),
    ("Accidente", ("choque", "colision", "accidente", "vuelco", "cierre vehicular", "trafico")),
    ("Robo", ("asalto", "robo", "hurto", "saqueo", "fraude electronico")),
    ("Corte de luz", ("corte de luz", "apagon", "sin energia")),
    ("Sospechoso", ("protesta", "disturbio", "operativo", "allanamiento", "sospechoso")),
]
OFFER_SOURCE_TYPES = {"offers_html", "offer_detail", "degusta_offers"}
OFFER_CATEGORY_NAME = "Oferta"
OFFER_TERMS = (
    "oferta", "promocion", "promoción", "descuento", "descuentos", "off",
    "2x1", "cupon", "cupón", "rebaja", "desde $", "por $", "solo $",
)
OFFER_ZONE_HINTS = (
    "bella vista", "obarrio", "san francisco", "costa del este", "marbella",
    "paitilla", "via españa", "via brasil", "costa sur", "albrook", "clayton",
    "casco antiguo", "avenida balboa", "el cangrejo", "panama oeste", "arraijan",
    "gorgona", "coronado", "costa verde", "brisas del golf", "westland",
    "chanis", "pueblo nuevo", "el dorado", "condado del rey", "villa lucre",
    "via porras", "multiplaza", "soho mall", "metromall",
)
ADDRESS_PATTERN = re.compile(
    r"((?:calle|avenida|av\.|ave\.|v[íi]a|plaza|ph|centro comercial|mall|local)\s+[^.\n]{8,140})",
    re.IGNORECASE,
)
MERCHANT_PATTERN = re.compile(
    r"(?:en|por|de|para)\s+([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ0-9&().,'\- ]{3,90})",
    re.IGNORECASE,
)

SEVERITY_RULES = [
    (5, ("muertos", "fatal", "evacuar", "cerrada", "cerrado", "explosion")),
    (4, ("incendio", "inundacion", "accidente", "colision", "deslizamiento", "robo")),
    (3, ("trafico", "congestion", "lluvia", "cierre", "protesta", "operativo")),
]

TTL_RULES = [
    (36, SERVICE_ALERT_TERMS),
    (12, ("trafico", "congestion", "cierre vehicular", "accidente", "desvio")),
    (18, ("lluvia", "inundacion", "protesta")),
    (24, ("incendio", "operativo", "hurto", "robo")),
]

AUDIENCE_RULES = [
    ("Gasolineras de Panama", ("gasolina", "combustible", "diesel")),
    ("Clinicas, hospitales y farmacias", ("medicamento", "farmacia", "hospital", "clinica", "salud")),
    ("Vias principales de Panama", ("trafico", "choque", "accidente", "cierre vehicular", "congestion")),
    ("Barrios y zonas residenciales", ("incendio", "inundacion", "lluvia", "robo")),
]

PANAMA_LOCATION_RULES = [
    {"keywords": ("obarrio",), "lat": 8.9877, "lng": -79.5230, "label": "Obarrio", "precision": "neighborhood"},
    {"keywords": ("bella vista",), "lat": 8.9826, "lng": -79.5288, "label": "Bella Vista", "precision": "neighborhood"},
    {"keywords": ("el cangrejo",), "lat": 8.9868, "lng": -79.5317, "label": "El Cangrejo", "precision": "neighborhood"},
    {"keywords": ("marbella",), "lat": 8.9804, "lng": -79.5195, "label": "Marbella", "precision": "neighborhood"},
    {"keywords": ("san francisco",), "lat": 8.9908, "lng": -79.5082, "label": "San Francisco", "precision": "neighborhood"},
    {"keywords": ("paitilla", "punta paitilla"), "lat": 8.9746, "lng": -79.5145, "label": "Paitilla", "precision": "neighborhood"},
    {"keywords": ("avenida balboa", "av balboa"), "lat": 8.9764, "lng": -79.5260, "label": "Avenida Balboa", "precision": "corridor"},
    {"keywords": ("via espana", "vía españa", "via españa"), "lat": 8.9864, "lng": -79.5199, "label": "Via Espana", "precision": "corridor"},
    {"keywords": ("tumba muerto", "via ricardo j alfaro", "vía ricardo j alfaro"), "lat": 9.0229, "lng": -79.5325, "label": "Tumba Muerto", "precision": "corridor"},
    {"keywords": ("transistmica", "via transistmica", "vía transístmica"), "lat": 9.0234, "lng": -79.5344, "label": "Via Transistmica", "precision": "corridor"},
    {"keywords": ("cinta costera",), "lat": 8.9736, "lng": -79.5274, "label": "Cinta Costera", "precision": "corridor"},
    {"keywords": ("calle 50",), "lat": 8.9827, "lng": -79.5208, "label": "Calle 50", "precision": "street"},
    {"keywords": ("calle 50 y", "calle 50 con"), "lat": 8.9831, "lng": -79.5215, "label": "Calle 50", "precision": "street"},
    {"keywords": ("calle 58 este",), "lat": 8.9837, "lng": -79.5201, "label": "Calle 58 Este", "precision": "street"},
    {"keywords": ("corredor sur",), "lat": 8.9898, "lng": -79.5008, "label": "Corredor Sur", "precision": "corridor"},
    {"keywords": ("corredor norte",), "lat": 9.0480, "lng": -79.5320, "label": "Corredor Norte", "precision": "corridor"},
    {"keywords": ("puente de las americas", "puente de las américas"), "lat": 8.9494, "lng": -79.5548, "label": "Puente de las Americas", "precision": "landmark"},
    {"keywords": ("albrook",), "lat": 8.9711, "lng": -79.5556, "label": "Albrook", "precision": "neighborhood"},
    {"keywords": ("arraijan", "arraiján"), "lat": 8.9512, "lng": -79.6607, "label": "Arraiján", "precision": "district"},
    {"keywords": ("la chorrera",), "lat": 8.8803, "lng": -79.7833, "label": "La Chorrera", "precision": "district"},
    {"keywords": ("capira",), "lat": 8.7611, "lng": -79.8794, "label": "Capira", "precision": "district"},
    {"keywords": ("chame",), "lat": 8.5775, "lng": -79.8847, "label": "Chame", "precision": "district"},
    {"keywords": ("san miguelito",), "lat": 9.0333, "lng": -79.5000, "label": "San Miguelito", "precision": "district"},
    {"keywords": ("tocumen",), "lat": 9.0833, "lng": -79.3833, "label": "Tocumen", "precision": "district"},
    {"keywords": ("pacora",), "lat": 9.0800, "lng": -79.2897, "label": "Pacora", "precision": "district"},
    {"keywords": ("chepo",), "lat": 9.1702, "lng": -79.1008, "label": "Chepo", "precision": "district"},
    {"keywords": ("chilibre",), "lat": 9.1500, "lng": -79.6167, "label": "Chilibre", "precision": "district"},
    {"keywords": ("colon", "colón"), "lat": 9.3545, "lng": -79.9001, "label": "Colon", "precision": "district"},
    {"keywords": ("sabanitas",), "lat": 9.3167, "lng": -79.8167, "label": "Sabanitas", "precision": "district"},
    {"keywords": ("david",), "lat": 8.4333, "lng": -82.4333, "label": "David", "precision": "district"},
    {"keywords": ("bugaba",), "lat": 8.4833, "lng": -82.6167, "label": "Bugaba", "precision": "district"},
    {"keywords": ("boquete",), "lat": 8.7802, "lng": -82.4338, "label": "Boquete", "precision": "district"},
    {"keywords": ("volcan", "volcán"), "lat": 8.7721, "lng": -82.6391, "label": "Volcan", "precision": "district"},
    {"keywords": ("santiago",), "lat": 8.1000, "lng": -80.9833, "label": "Santiago", "precision": "district"},
    {"keywords": ("penonome", "penonomé"), "lat": 8.5189, "lng": -80.3573, "label": "Penonome", "precision": "district"},
    {"keywords": ("aguadulce",), "lat": 8.2418, "lng": -80.5491, "label": "Aguadulce", "precision": "district"},
    {"keywords": ("chitre", "chitré"), "lat": 7.9667, "lng": -80.4333, "label": "Chitre", "precision": "district"},
    {"keywords": ("las tablas",), "lat": 7.7667, "lng": -80.2833, "label": "Las Tablas", "precision": "district"},
    {"keywords": ("changuinola",), "lat": 9.4333, "lng": -82.5167, "label": "Changuinola", "precision": "district"},
    {"keywords": ("bocas del toro",), "lat": 9.3403, "lng": -82.2420, "label": "Bocas del Toro", "precision": "district"},
    {"keywords": ("meteti",), "lat": 8.4983, "lng": -77.9786, "label": "Meteti", "precision": "district"},
    {"keywords": ("yaviza",), "lat": 8.1584, "lng": -77.6928, "label": "Yaviza", "precision": "district"},
    {"keywords": ("panama oeste",), "lat": 8.9512, "lng": -79.6607, "label": "Panama Oeste", "precision": "region"},
    {"keywords": ("panama norte",), "lat": 9.1500, "lng": -79.6167, "label": "Panama Norte", "precision": "region"},
    {"keywords": ("panama este",), "lat": 9.0800, "lng": -79.2897, "label": "Panama Este", "precision": "region"},
    {"keywords": ("capital",), "lat": 8.983333, "lng": -79.516667, "label": "Ciudad de Panama", "precision": "city"},
    {"keywords": ("panama", "panamá"), "lat": 8.983333, "lng": -79.516667, "label": "Ciudad de Panama", "precision": "city"},
]
LOCATION_PRECISION_WEIGHTS = {
    "city": 1,
    "region": 2,
    "district": 3,
    "neighborhood": 4,
    "corridor": 5,
    "landmark": 5,
    "street": 6,
}
OFFER_DETAIL_CACHE = {}
OFFER_GEOCODE_CACHE = {}
OFFER_PAGE_CACHE = {}


def _is_offer_source(source):
    return (source.get("type") or "").lower() in OFFER_SOURCE_TYPES or bool(source.get("offers_mode"))


def _json_load(path: Path, default):
    if not Path(path).exists():
        return default
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def _json_save(path: Path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_sources(path):
    return _json_load(Path(path), [])


def save_sources(path, sources):
    _json_save(Path(path), sources)
    return sources


def load_manifest(path):
    return _json_load(Path(path), {"items": []})


def save_manifest(path, payload):
    _json_save(Path(path), payload)
    return payload


def load_sync_state(path):
    return _json_load(Path(path), {"last_sync_at": None, "last_error": None})


def save_sync_state(path, payload):
    _json_save(Path(path), payload)
    return payload


def _fix_mojibake(value):
    text = str(value or "")
    if not any(token in text for token in ("Ã", "Â", "â", "\ufffd")):
        return text
    for source_enc, target_enc in (("latin-1", "utf-8"), ("cp1252", "utf-8")):
        try:
            repaired = text.encode(source_enc).decode(target_enc)
            if repaired.count("Ã") < text.count("Ã"):
                text = repaired
        except Exception:
            continue
    return text


def _strip_html(value):
    return re.sub(r"<[^>]+>", " ", str(value or ""))


def _clean_text(value, max_len=700):
    cleaned = _fix_mojibake(unescape(_strip_html(value)))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_len]


def _normalize_text(value):
    normalized = unicodedata.normalize("NFKD", _fix_mojibake(str(value or "")))
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", normalized).strip().lower()


def _html_items(base_url, html_text):
    candidates = []
    seen = set()
    html_text = _fix_mojibake(html_text)
    for match in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html_text, re.IGNORECASE | re.DOTALL):
        href, body = match.groups()
        title = _clean_text(body, 180)
        if len(title) < 35 or len(title) > 180:
            continue
        href = href.strip()
        if href.startswith("/"):
            href = base_url.rstrip("/") + href
        if not href.startswith("http"):
            continue
        key = (href, title)
        if key in seen:
            continue
        seen.add(key)
        candidates.append({
            "title": title,
            "summary": title,
            "link": href,
            "published_at": datetime.utcnow(),
        })
    return candidates[:30]


def _html_offer_items(base_url, html_text):
    candidates = []
    seen = set()
    html_text = _fix_mojibake(html_text)
    for match in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html_text, re.IGNORECASE | re.DOTALL):
        href, body = match.groups()
        attrs_text = match.group(0)
        title = _clean_text(body, 180)
        if len(title) < 8:
            for attr_name in ("title", "aria-label", "data-title", "alt"):
                attr_match = re.search(fr'{attr_name}="([^"]+)"', attrs_text, re.IGNORECASE)
                if attr_match:
                    title = _clean_text(attr_match.group(1), 180)
                    if len(title) >= 8:
                        break
        if len(title) > 180:
            title = title[:180]
        href = href.strip()
        href = urljoin(base_url, href)
        if not href.startswith("http"):
            continue
        snippet = _clean_text(html_text[max(0, match.start() - 240): match.end() + 1200], 1000)
        if len(title) < 8 and len(snippet) < 30:
            continue
        normalized = _normalize_text(f"{title}. {snippet}. {href}")
        if not any(term in normalized for term in OFFER_TERMS) and not re.search(
            r"/(oferta|ofertas|promocion|promociones|descuento|descuentos)/",
            href,
            re.IGNORECASE,
        ):
            continue
        key = href.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        candidates.append({
            "title": title or _clean_text(snippet[:160], 160),
            "summary": snippet,
            "link": href,
            "published_at": datetime.utcnow(),
        })
    return candidates[:40]


def _offer_detail_item(url, html_text):
    html_text = _fix_mojibake(html_text or "")
    title_match = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html_text, re.IGNORECASE)
    if not title_match:
        title_match = re.search(r"<title>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
    title = _clean_text(title_match.group(1) if title_match else url, 180)
    return [{
        "title": title,
        "summary": _clean_text(html_text, 1000),
        "link": url,
        "published_at": datetime.utcnow(),
    }]


def _offer_headers():
    return {"User-Agent": "PanamaAlertBot/1.0 (+offers-ingest)"}


def _fetch_offer_detail(link):
    import requests

    cache_key = (link or "").strip()
    if cache_key in OFFER_DETAIL_CACHE:
        return OFFER_DETAIL_CACHE[cache_key]
    try:
        response = requests.get(link, timeout=10, headers=_offer_headers())
        response.raise_for_status()
        response.encoding = response.encoding or response.apparent_encoding or "utf-8"
        html_text = response.text
        meta_bits = re.findall(
            r'<meta[^>]+(?:name|property)="(?:description|og:description|og:title)"[^>]+content="([^"]+)"',
            html_text,
            re.IGNORECASE,
        )
        title_bits = re.findall(r"<title>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
        detail = _clean_text(" ".join(meta_bits + title_bits + [html_text]), 2400)
        OFFER_DETAIL_CACHE[cache_key] = detail
        return detail
    except Exception:
        OFFER_DETAIL_CACHE[cache_key] = ""
        return ""


def _extract_offer_zone(title, summary):
    combined = _normalize_text(f"{title}. {summary}")
    title_match = re.search(r"\(([^)]+)\)", str(title or ""))
    if title_match:
        return _clean_text(title_match.group(1), 80)
    for zone in OFFER_ZONE_HINTS:
        if zone in combined:
            return zone.title()
    for mapping in PANAMA_LOCATION_RULES:
        for keyword in mapping["keywords"]:
            normalized_keyword = _normalize_text(keyword)
            if normalized_keyword and normalized_keyword in combined:
                return mapping["label"]
    return ""


def _extract_offer_address(text_value):
    match = ADDRESS_PATTERN.search(str(text_value or ""))
    if match:
        return _clean_text(match.group(1), 150)
    return ""


def _extract_offer_merchant(title, summary):
    raw_title = _clean_text(title, 180)
    summary_text = _clean_text(summary, 500)
    match = MERCHANT_PATTERN.search(f"{raw_title}. {summary_text}")
    if match:
        return _clean_text(match.group(1), 100)
    if "(" in raw_title:
        return _clean_text(raw_title.split("(")[0], 100)
    merchant_match = re.search(r"(?:cl[ií]nica|laboratorio|restaurante|cafe|caf[eé]|bar|hotel|spa|dental|lab)\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ0-9&().,'\- ]{2,80}", summary_text, re.IGNORECASE)
    if merchant_match:
        return _clean_text(merchant_match.group(0), 100)
    return ""


def _geocode_offer_query(query):
    import requests

    query = _clean_text(query, 180)
    if not query:
        return None
    cache_key = _normalize_text(query)
    if cache_key in OFFER_GEOCODE_CACHE:
        return OFFER_GEOCODE_CACHE[cache_key]
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": query,
                "format": "jsonv2",
                "limit": 1,
                "addressdetails": 1,
                "countrycodes": "pa",
            },
            headers=_offer_headers(),
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json() or []
    except Exception:
        OFFER_GEOCODE_CACHE[cache_key] = None
        return None
    if not payload:
        OFFER_GEOCODE_CACHE[cache_key] = None
        return None
    item = payload[0]
    if not item.get("lat") or not item.get("lon"):
        OFFER_GEOCODE_CACHE[cache_key] = None
        return None
    resolved = {
        "lat": float(item["lat"]),
        "lng": float(item["lon"]),
        "label": _clean_text(item.get("display_name") or query, 140),
    }
    OFFER_GEOCODE_CACHE[cache_key] = resolved
    return resolved


def _iter_source_urls(source):
    urls = []
    primary = _clean_text(source.get("url"), 600)
    if primary:
        urls.append(primary)
    for extra in source.get("extra_urls") or []:
        candidate = _clean_text(extra, 600)
        if candidate:
            urls.append(candidate)
    page_pattern = _clean_text(source.get("page_pattern"), 600)
    max_pages = max(1, int(source.get("max_pages") or 1))
    if page_pattern and "{page}" in page_pattern:
        for page in range(1, max_pages + 1):
            urls.append(page_pattern.format(page=page))

    seen = set()
    unique_urls = []
    for url in urls:
        key = url.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        unique_urls.append(url)
    return unique_urls


def _fetch_source_page(url):
    import requests

    cache_key = (url or "").strip()
    if cache_key in OFFER_PAGE_CACHE:
        return OFFER_PAGE_CACHE[cache_key]

    response = requests.get(
        cache_key,
        timeout=12,
        headers={"User-Agent": "PanamaAlertBot/1.0 (+news-ingest)"},
    )
    response.raise_for_status()
    response.encoding = response.encoding or response.apparent_encoding or "utf-8"
    OFFER_PAGE_CACHE[cache_key] = response.text
    return response.text


def _resolve_offer_location(source, item):
    detail_text = _fetch_offer_detail(item.get("link"))
    combined_text = " ".join(part for part in [
        item.get("title"),
        item.get("summary"),
        detail_text,
    ] if part)
    merchant = _extract_offer_merchant(item.get("title"), combined_text)
    address = _extract_offer_address(combined_text)
    zone = _extract_offer_zone(item.get("title"), combined_text)

    queries = []
    if merchant and address:
        queries.append(f"{merchant}, {address}, Panama")
    if merchant and address and zone:
        queries.append(f"{merchant}, {address}, {zone}, Panama")
    if address:
        queries.append(f"{address}, Panama")
    if merchant and zone:
        queries.append(f"{merchant}, {zone}, Panama")
    if address and zone:
        queries.append(f"{address}, {zone}, Panama")
    if merchant:
        queries.append(f"{merchant}, Panama")
    if zone:
        queries.append(f"{zone}, Panama")

    for query in queries:
        resolved = _geocode_offer_query(query)
        if resolved:
            return {
                **resolved,
                "merchant": merchant,
                "address": address,
                "zone": zone,
                "detail_text": detail_text,
            }
    return None


def _google_maps_offer_url(lat, lng, label=""):
    coords = f"{float(lat):.6f},{float(lng):.6f}"
    query = f"{label} {coords}".strip() if label else coords
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"


def _compact_offer_text(value, max_len=360):
    text = _clean_text(value, max_len * 2)
    if not text:
        return "Oferta detectada por el agente. Abre la fuente para confirmar vigencia, condiciones y disponibilidad."

    noise_patterns = (
        r"\bjavascript\b.*",
        r"\bcookies?\b.*",
        r"\biniciar sesi[oó]n\b.*",
        r"\bregistrate\b.*",
        r"\bnewsletter\b.*",
    )
    for pattern in noise_patterns:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" -|")

    if len(text) <= max_len:
        return text
    trimmed = text[:max_len].rsplit(" ", 1)[0].strip()
    return f"{trimmed}..."


def _format_offer_title(title, merchant, zone):
    clean_title = _clean_text(title, 130)
    clean_merchant = _clean_text(merchant, 70)
    clean_zone = _clean_text(zone, 45)

    if clean_merchant and clean_merchant.lower() not in clean_title.lower():
        candidate = f"Oferta: {clean_merchant} - {clean_title}"
    else:
        candidate = f"Oferta: {clean_title}" if clean_title else f"Oferta en {clean_merchant or clean_zone or 'Panama'}"

    if clean_zone and clean_zone.lower() not in candidate.lower():
        candidate = f"{candidate} ({clean_zone})"
    return _clean_text(candidate, 160)


def _format_offer_description(source, item, title, merchant, address, zone, detail_text, lat, lng):
    source_name = _clean_text(source.get("name") or "Fuente externa", 80)
    merchant_name = _clean_text(merchant or "Comercio detectado", 90)
    address_label = _clean_text(address or zone or "Ubicacion detectada en Panama", 120)
    zone_label = _clean_text(zone or address_label, 80)
    offer_summary = _compact_offer_text(detail_text or title, 380)
    source_url = _clean_text(item.get("link") or "", 300)
    maps_url = _google_maps_offer_url(lat, lng, address_label or merchant_name)

    parts = [
        f"[Fuente externa: {source_name}] Oferta detectada por PanamaAlert Bot.",
        f"Comercio: {merchant_name}.",
        f"Resumen: {offer_summary}",
        f"Ubicacion estimada: {address_label}.",
        f"Zona: {zone_label}.",
        "Recomendacion: confirma vigencia, horario y condiciones antes de ir.",
        f"Google Maps: {maps_url}",
    ]
    if source_url:
        parts.append(f"Fuente original: {source_url}")
    return "\n".join(parts)


def _parse_date(value):
    if not value:
        return datetime.utcnow()
    try:
        dt = parsedate_to_datetime(value)
        if getattr(dt, "tzinfo", None):
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except Exception:
        return datetime.utcnow()


def _infer_category(text_value):
    haystack = _normalize_text(text_value)
    for category, keywords in CATEGORY_RULES:
        if any(keyword in haystack for keyword in keywords):
            return category
    return "Sospechoso"


def _infer_severity(text_value):
    haystack = _normalize_text(text_value)
    for severity, keywords in SEVERITY_RULES:
        if any(keyword in haystack for keyword in keywords):
            return severity
    return 3


def _infer_ttl_hours(text_value, default_hours=18):
    haystack = _normalize_text(text_value)
    for hours, keywords in TTL_RULES:
        if any(keyword in haystack for keyword in keywords):
            return hours
    return default_hours


def _audience_label(text_value):
    haystack = _normalize_text(text_value)
    for label, keywords in AUDIENCE_RULES:
        if any(keyword in haystack for keyword in keywords):
            return label
    return DEFAULT_LOCATION_LABEL


def _fingerprint(source_name, item):
    basis = f"{source_name}|{item.get('link', '')}|{item.get('title', '')}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _source_location(source, text_value):
    normalized_text = _normalize_text(text_value)
    default_location = source.get("default_location") or {}
    best_match = None
    for mapping in source.get("location_keywords") or []:
        keyword = _normalize_text(mapping.get("keyword"))
        if keyword and keyword in normalized_text:
            candidate = {
                "lat": float(mapping.get("lat")),
                "lng": float(mapping.get("lng")),
                "label": _clean_text(mapping.get("label") or keyword.title(), 80),
                "score": 200 + len(keyword),
                "precision": "source_specific",
            }
            if not best_match or candidate["score"] > best_match["score"]:
                best_match = candidate
    for mapping in PANAMA_LOCATION_RULES:
        for keyword in mapping["keywords"]:
            normalized_keyword = _normalize_text(keyword)
            if normalized_keyword and normalized_keyword in normalized_text:
                precision = mapping.get("precision") or "district"
                candidate = {
                    "lat": float(mapping["lat"]),
                    "lng": float(mapping["lng"]),
                    "label": mapping["label"],
                    "score": (LOCATION_PRECISION_WEIGHTS.get(precision, 1) * 100) + len(normalized_keyword),
                    "precision": precision,
                }
                if not best_match or candidate["score"] > best_match["score"]:
                    best_match = candidate
    if best_match:
        return {
            "lat": best_match["lat"],
            "lng": best_match["lng"],
            "label": best_match["label"],
            "is_default": False,
            "precision": best_match.get("precision", "district"),
        }
    if "lat" in default_location and "lng" in default_location:
        return {
            "lat": float(default_location["lat"]),
            "lng": float(default_location["lng"]),
            "label": _clean_text(default_location.get("label") or source.get("name") or DEFAULT_LOCATION_LABEL, 80),
            "is_default": True,
            "precision": "default",
        }
    return {**DEFAULT_CENTER, "is_default": True, "precision": "default"}


def _has_location_signal(normalized_text):
    if any(keyword in normalized_text for keyword in LOCATION_HINTS):
        return True
    return any(
        _normalize_text(keyword) in normalized_text
        for mapping in PANAMA_LOCATION_RULES
        for keyword in mapping["keywords"]
    )


def _has_street_level_signal(normalized_text):
    return any(keyword in normalized_text for keyword in STREET_LEVEL_HINTS)


def _has_operational_impact(normalized_text):
    return any(keyword in normalized_text for keyword in OPERATIONAL_IMPACT_TERMS)


def _is_service_alert(normalized_text):
    return any(keyword in normalized_text for keyword in SERVICE_ALERT_TERMS)


def _is_actionable(text_value):
    haystack = _normalize_text(text_value)
    if any(keyword in haystack for keyword in IRRELEVANT_KEYWORDS):
        return False
    if any(keyword in haystack for keyword in LOW_SIGNAL_NEWS):
        return False
    if not any(keyword in haystack for _, keywords in CATEGORY_RULES for keyword in keywords):
        return False
    if _is_service_alert(haystack):
        return _has_location_signal(haystack) or _has_operational_impact(haystack)
    return _has_location_signal(haystack) and _has_operational_impact(haystack)


def _sanitize_xml_payload(raw_text):
    fixed = _fix_mojibake(raw_text or "")
    fixed = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9a-fA-F]+;)", "&amp;", fixed)
    return fixed


def fetch_source_items(source):
    source_type = (source.get("type") or "rss").lower()
    url = source.get("url")
    if not url:
        raise ValueError("La fuente necesita url")

    if source_type == "instagram":
        return []

    if source_type in {"offers_html", "degusta_offers"}:
        items = []
        seen = set()
        for page_url in _iter_source_urls(source):
            html_text = _fetch_source_page(page_url)
            for item in _html_offer_items(page_url, html_text):
                key = (item.get("link") or "").rstrip("/")
                if key in seen:
                    continue
                seen.add(key)
                items.append(item)
        return items

    if source_type == "offer_detail":
        items = []
        seen = set()
        for page_url in _iter_source_urls(source):
            html_text = _fetch_source_page(page_url)
            for item in _offer_detail_item(page_url, html_text):
                key = (item.get("link") or "").rstrip("/")
                if key in seen:
                    continue
                seen.add(key)
                items.append(item)
        return items

    response_text = _fetch_source_page(url)

    if source_type == "html":
        return _html_items(url, response_text)

    if source_type != "rss":
        raise ValueError("Tipo de fuente no soportado")

    raw_xml = _sanitize_xml_payload(response_text)
    root = ET.fromstring(raw_xml)
    items = []
    for item in root.findall(".//item"):
        items.append({
            "title": _clean_text(item.findtext("title"), 160),
            "summary": _clean_text(item.findtext("description"), 700),
            "link": _clean_text(item.findtext("link"), 300),
            "published_at": _parse_date(item.findtext("pubDate")),
        })
    return items


def build_ping_payload(source, item):
    if _is_offer_source(source):
        title = _clean_text(item.get("title"), 160)
        summary = _clean_text(item.get("summary"), 850)
        location = _resolve_offer_location(source, item)
        if not location:
            return None
        merchant = location.get("merchant") or source.get("name") or "Oferta"
        zone = location.get("zone") or location.get("label") or "Panamá"
        address = location.get("address") or location.get("label") or zone
        detail_text = _clean_text(location.get("detail_text") or summary, 900)
        display_title = _format_offer_title(title, merchant, zone)
        description = _format_offer_description(
            source,
            item,
            title,
            merchant,
            address,
            zone,
            detail_text,
            location["lat"],
            location["lng"],
        )
        return {
            "fingerprint": _fingerprint(source.get("name") or "source", item),
            "title": display_title[:160],
            "description": description,
            "category_name": OFFER_CATEGORY_NAME,
            "severity": 1,
            "lat": float(location["lat"]),
            "lng": float(location["lng"]),
            "location_label": address,
            "audience_label": "Ofertas y descuentos en comercios",
            "expires_at": (item.get("published_at") or datetime.utcnow()) + timedelta(hours=max(24, int(source.get("ttl_hours") or 48))),
            "source_name": source.get("name") or "Fuente externa",
            "source_url": item.get("link"),
            "published_at": (item.get("published_at") or datetime.utcnow()),
        }

    title = _clean_text(item.get("title"), 160)
    summary = _clean_text(item.get("summary"), 850)
    text_value = f"{title}. {summary}"
    if not _is_actionable(text_value):
        return None
    location = _source_location(source, text_value)
    normalized_text = _normalize_text(text_value)
    normalized_location_label = _normalize_text(location.get("label") or "")
    if location.get("is_default"):
        return None
    if normalized_location_label in GENERIC_LOCATION_LABELS:
        return None
    precision_weight = LOCATION_PRECISION_WEIGHTS.get(location.get("precision"), 0)
    has_street_signal = _has_street_level_signal(normalized_text)
    if precision_weight < 3:
        return None
    if (
        precision_weight == 3
        and normalized_location_label in METRO_BROAD_LOCATION_LABELS
        and not has_street_signal
        and not _is_service_alert(normalized_text)
    ):
        return None
    ttl_hours = int(source.get("ttl_hours") or _infer_ttl_hours(text_value))
    audience_label = _audience_label(text_value)
    return {
        "fingerprint": _fingerprint(source.get("name") or "source", item),
        "title": title,
        "description": f"[Fuente externa: {source.get('name')}] {summary}\nMas info: {item.get('link')}",
        "category_name": _infer_category(text_value),
        "severity": _infer_severity(text_value),
        "lat": float(location["lat"]),
        "lng": float(location["lng"]),
        "location_label": location.get("label") or source.get("name") or DEFAULT_LOCATION_LABEL,
        "audience_label": audience_label,
        "expires_at": (item.get("published_at") or datetime.utcnow()) + timedelta(hours=max(4, ttl_hours)),
        "source_name": source.get("name") or "Fuente externa",
        "source_url": item.get("link"),
        "published_at": (item.get("published_at") or datetime.utcnow()),
    }


def _apply_ping_to_incident(incident, ping):
    incident.title = ping["title"][:160]
    incident.description = (
        f"{ping['description'][:820]}\nZona objetivo: {ping['location_label']}\nAudiencia: {ping['audience_label']}"
    )[:1000]
    incident.lat = ping["lat"]
    incident.lng = ping["lng"]
    incident.severity = ping["severity"]
    incident.status = "verified"
    incident.expires_at = ping["expires_at"]


def _ensure_news_user(db_session, models):
    User, Role = models
    user = User.query.filter_by(username="newsbot").first()
    if user:
        return user
    role = Role.query.filter_by(name="admin").first() or Role.query.filter_by(name="moderator").first() or Role.query.filter_by(name="user").first()
    if not role:
        role = Role(name="admin", description="Sistema de noticias")
        db_session.add(role)
        db_session.flush()
    user = User(
        username="newsbot",
        email="newsbot@panamaalert.local",
        password_hash="newsbot-disabled",
        full_name="PanamaAlert News Bot",
        role_id=role.id,
        email_verified=True,
        is_active=False,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _ensure_category(db_session, IncidentCategory, categories, name):
    if name in categories:
        return categories[name]
    category = IncidentCategory(
        name=name,
        icon="rss",
        color_hex="#2563eb" if name == "Aviso ciudadano" else "#64748b",
        default_severity=2 if name == "Aviso ciudadano" else 3,
    )
    db_session.add(category)
    db_session.flush()
    categories[name] = category.id
    return category.id


def sync_sources(db_session, models, categories, manifest_path, sources):
    User, Role, Incident, IncidentCategory = models
    manifest = load_manifest(manifest_path)
    known = {item["fingerprint"]: item for item in manifest.get("items", []) if item.get("active", True)}
    news_user = _ensure_news_user(db_session, (User, Role))

    synced = []
    errors = []
    for source in sources:
        if not source.get("enabled", True):
            continue
        try:
            items = fetch_source_items(source)
        except Exception as exc:
            errors.append({"source": source.get("name"), "error": str(exc)})
            continue
        accepted_for_source = 0
        max_items = max(1, int(source.get("max_items", 12)))
        candidate_scan_limit = max_items * (10 if _is_offer_source(source) else 3)
        for raw_item in items[:candidate_scan_limit]:
            fingerprint = _fingerprint(source.get("name") or "source", raw_item)
            ping = build_ping_payload(source, raw_item)
            if not ping:
                existing = known.get(fingerprint)
                if existing and existing.get("active", True):
                    incident = Incident.query.get(existing.get("incident_id"))
                    if incident and incident.status != "dismissed":
                        incident.status = "dismissed"
                    existing["active"] = False
                continue
            existing = known.get(ping["fingerprint"])
            if existing:
                incident = Incident.query.get(existing.get("incident_id"))
                if incident and existing.get("active", True):
                    _apply_ping_to_incident(incident, ping)
                    synced.append({
                        "incident_id": int(incident.id),
                        "title": ping["title"],
                        "source_name": ping["source_name"],
                        "expires_at": ping["expires_at"].isoformat(),
                        "updated": True,
                    })
                    accepted_for_source += 1
                continue
            category_id = _ensure_category(db_session, IncidentCategory, categories, ping["category_name"])
            incident = Incident(user_id=news_user.id, category_id=category_id)
            _apply_ping_to_incident(incident, ping)
            db_session.add(incident)
            db_session.flush()
            manifest.setdefault("items", []).append({
                "fingerprint": ping["fingerprint"],
                "incident_id": int(incident.id),
                "source_name": ping["source_name"],
                "source_url": ping["source_url"],
                "published_at": ping["published_at"].isoformat(),
                "expires_at": ping["expires_at"].isoformat(),
                "active": True,
            })
            synced.append({
                "incident_id": int(incident.id),
                "title": ping["title"],
                "source_name": ping["source_name"],
                "expires_at": ping["expires_at"].isoformat(),
            })
            accepted_for_source += 1
            if accepted_for_source >= max_items:
                break

    save_manifest(manifest_path, manifest)
    return {"created": synced, "count": len(synced), "errors": errors}


def cleanup_expired_news_incidents(db_session, Incident, manifest_path):
    manifest = load_manifest(manifest_path)
    changed = 0
    now = datetime.utcnow()
    for item in manifest.get("items", []):
        if not item.get("active", True):
            continue
        expires_at = item.get("expires_at")
        try:
            expires_dt = datetime.fromisoformat(expires_at)
        except Exception:
            continue
        if expires_dt > now:
            continue
        incident = Incident.query.get(item.get("incident_id"))
        if incident and incident.status != "dismissed":
            incident.status = "dismissed"
            changed += 1
        item["active"] = False
    if changed:
        db_session.flush()
    save_manifest(manifest_path, manifest)
    return changed


def should_run_sync(state_path, min_minutes):
    state = load_sync_state(state_path)
    last_sync_at = state.get("last_sync_at")
    if not last_sync_at:
        return True
    try:
        last_sync = datetime.fromisoformat(last_sync_at)
    except Exception:
        return True
    return (datetime.utcnow() - last_sync) >= timedelta(minutes=max(1, int(min_minutes or 1)))


def maybe_auto_sync_news(
    db_session,
    models,
    categories,
    sources_path,
    manifest_path,
    state_path,
    min_minutes,
):
    if not should_run_sync(state_path, min_minutes):
        return {"triggered": False, "reason": "cooldown"}

    sources = load_sources(sources_path)
    if not sources:
        save_sync_state(state_path, {"last_sync_at": datetime.utcnow().isoformat(), "last_error": "Sin fuentes configuradas"})
        return {"triggered": False, "reason": "no_sources"}

    try:
        expired_removed = cleanup_expired_news_incidents(db_session, models[2], manifest_path)
        sync_result = sync_sources(db_session, models, categories, manifest_path, sources)
        db_session.commit()
        save_sync_state(state_path, {"last_sync_at": datetime.utcnow().isoformat(), "last_error": None})
        return {"triggered": True, "expired_removed": expired_removed, **sync_result}
    except Exception as exc:
        db_session.rollback()
        save_sync_state(state_path, {"last_sync_at": datetime.utcnow().isoformat(), "last_error": str(exc)})
        return {"triggered": False, "reason": "error", "error": str(exc)}
