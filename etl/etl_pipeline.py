"""
ETL PanamaAlert
===============
Extract  : CSV/JSON locales o endpoints HTTP de fuentes públicas (911 abiertos,
           datos abiertos municipales, feeds de noticias).
Transform: limpieza, geocodificación inversa básica (district matching),
           normalización a categorías canónicas + severidad.
Load     : staging -> incidents (vía SP sp_create_incident para reusar reglas).

Uso:
    python etl/etl_pipeline.py --source samples/incidents_sample.csv
    python etl/etl_pipeline.py --url https://datos.gob.pa/dataset/...

Programación (cron Linux OL8):
    */15 * * * * /usr/bin/python3 /opt/panama_alert/etl/etl_pipeline.py \
                  --source /opt/panama_alert/etl/incoming/*.csv
"""
import argparse
import csv
import glob
import json
import os
import sys
import time
from datetime import datetime

import pymysql

DB = dict(
    host=os.getenv("DB_HOST", "127.0.0.1"),
    port=int(os.getenv("DB_PORT", "3306")),
    user=os.getenv("DB_USER", "panama_alert"),
    password=os.getenv("DB_PASS", "panama_alert"),
    database=os.getenv("DB_NAME", "panama_alert"),
    charset="utf8mb4",
    autocommit=False,
)

# Mapeo de categorías heterogéneas → catálogo canónico
CATEGORY_MAP = {
    "robbery": "Robo", "robo": "Robo", "asalto": "Robo", "theft": "Robo",
    "accident": "Accidente", "crash": "Accidente", "choque": "Accidente",
    "fire": "Incendio", "incendio": "Incendio",
    "flood": "Inundación", "inundacion": "Inundación", "inundación": "Inundación",
    "suspicious": "Sospechoso", "vandalism": "Vandalismo",
    "medical": "Emergencia médica", "outage": "Corte de luz",
}

DEFAULT_USER = os.getenv("ETL_USER_ID", "1")  # admin


def conn():
    return pymysql.connect(**DB)


def start_run(c, source: str) -> int:
    with c.cursor() as cur:
        cur.execute("INSERT INTO etl_runs(source) VALUES (%s)", (source,))
        c.commit()
        return cur.lastrowid


def finish_run(c, run_id: int, read_n, ok_n, fail_n, status, message=None):
    with c.cursor() as cur:
        cur.execute("""UPDATE etl_runs
                          SET finished_at=NOW(), rows_read=%s, rows_loaded=%s,
                              rows_failed=%s, status=%s, message=%s
                        WHERE id=%s""",
                    (read_n, ok_n, fail_n, status, message, run_id))
        c.commit()


def stage_row(c, run_id, source, raw):
    with c.cursor() as cur:
        cur.execute(
            "INSERT INTO etl_staging_incidents(run_id, source, external_id, raw_json) "
            "VALUES (%s, %s, %s, %s)",
            (run_id, source, raw.get("id"), json.dumps(raw, ensure_ascii=False))
        )
        c.commit()


def get_category_id(c, raw_name: str) -> int | None:
    if not raw_name: return None
    key = raw_name.strip().lower()
    canonical = CATEGORY_MAP.get(key, raw_name.strip().capitalize())
    with c.cursor() as cur:
        cur.execute("SELECT id FROM incident_categories WHERE LOWER(name)=LOWER(%s)", (canonical,))
        row = cur.fetchone()
        return row[0] if row else None


def find_district_id(c, lat: float, lng: float) -> int | None:
    """Stub: en producción usar PostGIS / shapefile. Aquí district por nombre opcional."""
    return None


def transform(raw: dict) -> dict | None:
    try:
        lat = float(raw.get("lat") or raw.get("latitude"))
        lng = float(raw.get("lng") or raw.get("longitude"))
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    desc = (raw.get("description") or raw.get("desc") or raw.get("title") or "Reporte importado")[:1000]
    title = (raw.get("title") or desc[:80])[:160]
    severity = int(raw.get("severity") or 3)
    severity = max(1, min(5, severity))
    return {
        "title": title, "description": desc, "lat": lat, "lng": lng,
        "severity": severity, "category": raw.get("category") or raw.get("type") or "Sospechoso",
    }


def load_one(c, run_id, raw, transformed) -> bool:
    cat_id = get_category_id(c, transformed["category"])
    if not cat_id:
        with c.cursor() as cur:
            cur.execute("UPDATE etl_staging_incidents SET error=%s WHERE run_id=%s AND raw_json=%s LIMIT 1",
                        ("categoría desconocida", run_id, json.dumps(raw, ensure_ascii=False)))
            c.commit()
        return False
    dist_id = find_district_id(c, transformed["lat"], transformed["lng"])
    with c.cursor() as cur:
        cur.execute("SET @new_id = 0")
        cur.execute(
            "CALL sp_create_incident(%s,%s,%s,%s,%s,%s,%s,%s,@new_id)",
            (DEFAULT_USER, cat_id, dist_id, transformed["title"],
             transformed["description"], transformed["lat"], transformed["lng"],
             transformed["severity"])
        )
        cur.execute("UPDATE etl_staging_incidents SET processed=1 "
                    "WHERE run_id=%s AND raw_json=%s LIMIT 1",
                    (run_id, json.dumps(raw, ensure_ascii=False)))
        c.commit()
    return True


def extract_csv(path: str):
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            yield row

def extract_json(path: str):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        yield from data
    elif isinstance(data, dict) and "items" in data:
        yield from data["items"]


def process_file(path: str):
    print(f"[ETL] procesando {path}")
    c = conn()
    run_id = start_run(c, os.path.basename(path))
    read_n = ok_n = fail_n = 0
    try:
        rows = extract_csv(path) if path.lower().endswith(".csv") else extract_json(path)
        for raw in rows:
            read_n += 1
            stage_row(c, run_id, os.path.basename(path), raw)
            t = transform(raw)
            if not t:
                fail_n += 1
                continue
            try:
                if load_one(c, run_id, raw, t):
                    ok_n += 1
                else:
                    fail_n += 1
            except Exception as e:
                fail_n += 1
                print(f"[ETL] fila fallo: {e}")
        finish_run(c, run_id, read_n, ok_n, fail_n, "success")
        print(f"[ETL] OK leidas={read_n} cargadas={ok_n} fallidas={fail_n}")
    except Exception as e:
        finish_run(c, run_id, read_n, ok_n, fail_n, "failed", str(e)[:500])
        print(f"[ETL] FALLO: {e}", file=sys.stderr)
    finally:
        c.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, help="archivo CSV/JSON o glob")
    args = p.parse_args()
    files = glob.glob(args.source) or [args.source]
    for f in files:
        process_file(f)


if __name__ == "__main__":
    main()
