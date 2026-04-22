import io
import importlib.util
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]


def load_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, BASE_DIR / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


evidence_module = load_module("evidence_service", "app/services/evidence.py")
preferences_module = load_module("preferences_service", "app/services/preferences.py")
trust_module = load_module("trust_service", "app/services/trust.py")
news_module = load_module("news_service", "app/services/news_ingest.py")

list_incident_evidence = evidence_module.list_incident_evidence
save_incident_evidence = evidence_module.save_incident_evidence
load_preferences = preferences_module.load_preferences
save_preferences = preferences_module.save_preferences
should_notify = preferences_module.should_notify
explain_analysis = trust_module.explain_analysis
build_ping_payload = news_module.build_ping_payload
is_actionable = news_module._is_actionable
load_sync_state = news_module.load_sync_state
save_sync_state = news_module.save_sync_state
should_run_sync = news_module.should_run_sync
iter_source_urls = news_module._iter_source_urls


class FakeStorage:
    def __init__(self, content, filename, content_type):
        self.stream = io.BytesIO(content)
        self.filename = filename
        self.mimetype = content_type

    def save(self, target):
        Path(target).write_bytes(self.stream.getvalue())


class PreferencesServiceTest(unittest.TestCase):
    def test_preferences_roundtrip_and_filtering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prefs = save_preferences(root, 12, {
                "push_enabled": True,
                "email_enabled": False,
                "browser_notifications": True,
                "min_alert_level": "high",
                "incident_types": ["Incendio"],
            })
            self.assertTrue(prefs["browser_notifications"])
            loaded = load_preferences(root, 12)
            self.assertEqual(loaded["min_alert_level"], "high")
            self.assertFalse(should_notify(loaded, {"severity": 2, "category": "Incendio"}))
            self.assertTrue(should_notify(loaded, {"severity": 5, "category": "Incendio"}))
            self.assertFalse(should_notify(loaded, {"severity": 5, "category": "Robo"}))


class EvidenceServiceTest(unittest.TestCase):
    def test_saves_and_lists_incident_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            file_obj = FakeStorage(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01", "evidencia.jpg", "image/jpeg")
            item = save_incident_evidence(
                file_obj,
                incident_id=99,
                user_id=7,
                root=Path(tmp),
                max_bytes=1024 * 1024,
                allowed_extensions={"jpg", "jpeg", "png"},
                max_files=4,
            )
            self.assertEqual(item["kind"], "image")
            listed = list_incident_evidence(Path(tmp), 99)
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["filename"], "evidencia.jpg")

    def test_rejects_spoofed_media_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad_file = FakeStorage(b"<script>alert(1)</script>", "evidencia.jpg", "image/jpeg")
            with self.assertRaises(ValueError):
                save_incident_evidence(
                    bad_file,
                    incident_id=100,
                    user_id=7,
                    root=Path(tmp),
                    max_bytes=1024 * 1024,
                    allowed_extensions={"jpg", "jpeg", "png"},
                    max_files=4,
                )


class TrustExplainabilityTest(unittest.TestCase):
    def test_explain_analysis_distinguishes_ai_and_rules(self):
        reporter = {"credibility_label": "Credibilidad alta", "total_reports": 8}
        ai_view = explain_analysis({"status": "verified"}, {"confidence": 0.84, "flags": ["duplicate"]}, reporter)
        self.assertEqual(ai_view["source_mode"], "ai")
        self.assertEqual(ai_view["confidence_percent"], 84)
        rules_view = explain_analysis({"status": "pending"}, None, reporter)
        self.assertEqual(rules_view["source_mode"], "rules")
        self.assertIsNone(rules_view["confidence_percent"])


class NewsIngestTest(unittest.TestCase):
    def test_offer_source_urls_expand_and_dedupe(self):
        source = {
            "url": "https://example.com/ofertas",
            "extra_urls": ["https://example.com/ofertas", "https://example.com/promociones"],
            "page_pattern": "https://example.com/page/{page}",
            "max_pages": 3,
        }
        urls = iter_source_urls(source)
        self.assertEqual(urls, [
            "https://example.com/ofertas",
            "https://example.com/promociones",
            "https://example.com/page/1",
            "https://example.com/page/2",
            "https://example.com/page/3",
        ])

    def test_build_ping_payload_assigns_ttl_category_and_location(self):
        source = {
            "name": "Telemetro RSS",
            "ttl_hours": 10,
            "default_location": {"lat": 8.98, "lng": -79.52, "label": "Panamá"},
            "location_keywords": [{"keyword": "arraijan", "lat": 8.95, "lng": -79.66, "label": "Arraiján"}],
        }
        payload = build_ping_payload(source, {
            "title": "Accidente y tráfico intenso en Arraijan",
            "summary": "Se reporta colision vehicular con cierre parcial",
            "link": "https://example.com/noticia",
        })
        self.assertEqual(payload["category_name"], "Accidente")
        self.assertEqual(payload["severity"], 4)
        self.assertEqual(payload["location_label"], "Arraiján")
        self.assertEqual(payload["audience_label"], "Vias principales de Panama")
        self.assertGreater(payload["expires_at"], payload["published_at"])

    def test_filters_irrelevant_macro_or_animals_news(self):
        self.assertFalse(is_actionable("Subio la economia del pais y mejoro el PIB"))
        self.assertFalse(is_actionable("Aves nuevas fueron descubiertas en el pais"))
        self.assertFalse(is_actionable("Aumento de gasolina impacta gasolineras del pais"))
        self.assertTrue(is_actionable("Accidente con cierre parcial en Arraijan provoca trafico intenso"))

    def test_builtin_panama_location_rules_place_ping_by_news_text(self):
        source = {
            "name": "TVN Noticias",
            "ttl_hours": 12,
            "default_location": {"lat": 8.98, "lng": -79.52, "label": "Panamá"},
            "location_keywords": [],
        }
        payload = build_ping_payload(source, {
            "title": "Incendio cerca del mercado de David genera evacuaciones",
            "summary": "Bomberos atienden humo intenso en la zona",
            "link": "https://example.com/david",
        })
        self.assertEqual(payload["location_label"], "David")
        self.assertAlmostEqual(payload["lat"], 8.4333, places=3)
        self.assertAlmostEqual(payload["lng"], -82.4333, places=3)

    def test_prefers_precise_city_locations_over_generic_panama_mentions(self):
        source = {
            "name": "La Prensa",
            "ttl_hours": 12,
            "default_location": {"lat": 8.98, "lng": -79.52, "label": "Panamá"},
            "location_keywords": [],
        }
        payload = build_ping_payload(source, {
            "title": "Incendio en Calle 50, Obarrio, genera cierre parcial",
            "summary": "Bomberos atienden humo intenso y congestion vehicular en la zona",
            "link": "https://example.com/obarrio",
        })
        self.assertEqual(payload["location_label"], "Calle 50")
        self.assertAlmostEqual(payload["lat"], 8.9827, places=3)
        self.assertAlmostEqual(payload["lng"], -79.5208, places=3)

    def test_rejects_generic_capital_locations(self):
        source = {
            "name": "La Estrella",
            "ttl_hours": 18,
            "default_location": {"lat": 8.98, "lng": -79.52, "label": "Panama, Panama"},
            "location_keywords": [],
        }
        self.assertIsNone(build_ping_payload(source, {
            "title": "Operacion en la capital deja aprehendidos por robo",
            "summary": "La policia mantiene operativo en la capital",
            "link": "https://example.com/capital",
        }))

    def test_rejects_broad_metro_locations_without_street_or_landmark(self):
        source = {
            "name": "Telemetro",
            "ttl_hours": 18,
            "default_location": {"lat": 8.98, "lng": -79.52, "label": "Panama, Panama"},
            "location_keywords": [],
        }
        self.assertIsNone(build_ping_payload(source, {
            "title": "Robo en San Miguelito deja operativo policial",
            "summary": "Las autoridades mantienen presencia en la zona",
            "link": "https://example.com/sanmiguelito",
        }))

    def test_repairs_mojibake_and_rejects_generic_safety_content(self):
        source = {
            "name": "La Estrella",
            "ttl_hours": 18,
            "default_location": {"lat": 8.98, "lng": -79.52, "label": "Panamá"},
            "location_keywords": [],
        }
        payload = build_ping_payload(source, {
            "title": "OperaciÃ³n en ColÃ³n deja via cerrada por robo",
            "summary": "La policia mantiene operativo y congestion en la zona",
            "link": "https://example.com/colon",
        })
        self.assertEqual(payload["location_label"], "Colon")
        self.assertIn("Operación", payload["title"])
        self.assertIsNone(build_ping_payload(source, {
            "title": "Alerta en los bancos por fraudes electronicos: como protegerse de robos y estafas",
            "summary": "Consejos generales para clientes",
            "link": "https://example.com/bancos",
        }))

    def test_sync_cooldown_uses_state_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "sync_state.json"
            self.assertTrue(should_run_sync(state_path, 20))
            save_sync_state(state_path, {
                "last_sync_at": datetime.utcnow().isoformat(),
                "last_error": None,
            })
            state = load_sync_state(state_path)
            self.assertIsNotNone(state["last_sync_at"])
            self.assertFalse(should_run_sync(state_path, 20))
            save_sync_state(state_path, {
                "last_sync_at": (datetime.utcnow() - timedelta(minutes=25)).isoformat(),
                "last_error": "timeout",
            })
            self.assertTrue(should_run_sync(state_path, 20))


if __name__ == "__main__":
    unittest.main()
