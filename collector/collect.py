"""
collect.py — Collecte horaire du temps de trajet via Google Maps Distance Matrix API
Écrit les données dans Google Sheets via l'API REST v4.
"""

import os
import datetime
import requests
import google.auth
import google.auth.transport.requests
import zoneinfo

SEGMENTS = [
    {
        "name": "Troncon_RondPointAlex_MairieThones",
        "origin": "45.89168702079083, 6.251281047403949",
        "destination": "45.88199670566962, 6.324809885145161",
    },
    {
        "name": "Troncon_SallonDesDames_MairieThones",
        "origin": "45.90603714406791, 6.421877941967397",
        "destination": "45.88199670566962, 6.324809885145161",
    },
    {
        "name": "Troncon_GareAnnecy_MairieThones",
        "origin": "45.901535520060776, 6.121084193621739",
        "destination": "45.88199670566962, 6.324809885145161",
    },
]

SHEET_NAME = "traficdata"
HEADER = [
    "timestamp_utc", "timestamp_local", "segment",
    "duration_normal_s", "duration_traffic_s",
    "duration_normal_min", "duration_traffic_min",
    "delay_min", "distance_m", "distance_km",
    "traffic_ratio", "status",
]

BASE_URL = "https://sheets.googleapis.com/v4/spreadsheets"


def get_token():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds, _ = google.auth.default(scopes=scopes)
    auth_req = google.auth.transport.requests.Request()
    creds.refresh(auth_req)
    print(f"✓ Token obtenu, type: {type(creds).__name__}")
    return creds.token


def api_call(method, path, token, body=None, params=None):
    url = f"{BASE_URL}/{path}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.request(method, url, headers=headers, json=body, params=params, timeout=15)
    return resp


def create_sheet_if_not_exists(sheet_id, token):
    """Crée l'onglet s'il n'existe pas via batchUpdate."""
    # Vérifie d'abord si l'onglet existe
    resp = api_call("GET", sheet_id, token)
    if resp.status_code == 200:
        sheets = resp.json().get("sheets", [])
        for s in sheets:
            if s["properties"]["title"] == SHEET_NAME:
                print(f"✓ Onglet '{SHEET_NAME}' existe déjà.")
                return
    # Crée l'onglet
    body = {
        "requests": [
            {"addSheet": {"properties": {"title": SHEET_NAME}}}
        ]
    }
    resp = api_call("POST", f"{sheet_id}:batchUpdate", token, body)
    if resp.status_code == 200:
        print(f"✓ Onglet '{SHEET_NAME}' créé.")
    else:
        print(f"Note création onglet: {resp.status_code} {resp.text[:200]}")


def ensure_header(sheet_id, token):
    """Écrit l'en-tête si la première ligne est vide."""
    resp = api_call("GET", f"{sheet_id}/values/{SHEET_NAME}!A1:L1", token)
    if resp.status_code == 200:
        values = resp.json().get("values", [])
        if values and values[0] == HEADER:
            print("✓ En-têtes déjà présents.")
            return
    # Écriture via append sur ligne 1
    body = {"values": [HEADER], "majorDimension": "ROWS"}
    resp = api_call(
        "POST",
        f"{sheet_id}/values/{SHEET_NAME}!A1:append",
        token, body,
        params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"}
    )
    if resp.status_code == 200:
        print("✓ En-têtes ajoutés.")
    else:
        print(f"Note en-têtes: {resp.status_code} {resp.text[:200]}")


def append_rows(sheet_id, token, rows):
    """Ajoute des lignes à la suite du sheet."""
    body = {"values": rows, "majorDimension": "ROWS"}
    resp = api_call(
        "POST",
        f"{sheet_id}/values/{SHEET_NAME}!A1:append",
        token, body,
        params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"}
    )
    if resp.status_code != 200:
        raise Exception(f"Sheets append error {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def get_travel_time(api_key, origin, destination):
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": origin,
        "destinations": destination,
        "departure_time": "now",
        "traffic_model": "best_guess",
        "key": api_key,
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data["status"] != "OK":
        raise ValueError(f"API status: {data['status']}")
    element = data["rows"][0]["elements"][0]
    if element["status"] != "OK":
        raise ValueError(f"Element status: {element['status']}")
    dn = element["duration"]["value"]
    dt = element.get("duration_in_traffic", element["duration"])["value"]
    dm = element["distance"]["value"]
    return {
        "duration_normal_s": dn,
        "duration_traffic_s": dt,
        "duration_normal_min": round(dn / 60, 1),
        "duration_traffic_min": round(dt / 60, 1),
        "delay_min": round((dt - dn) / 60, 1),
        "distance_m": dm,
        "distance_km": round(dm / 1000, 2),
        "traffic_ratio": round(dt / dn, 3),
        "status": "OK",
    }


def main():
    api_key  = os.environ["GMAPS_API_KEY"]
    sheet_id = os.environ["GSHEET_ID"]

    ts_utc   = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    tz = zoneinfo.ZoneInfo("Europe/Paris")
    ts_local = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

    print(f"[{ts_utc}] Collecte en cours pour {len(SEGMENTS)} tronçon(s)...")

    token = get_token()
    create_sheet_if_not_exists(sheet_id, token)
    ensure_header(sheet_id, token)

    rows_to_append = []
    for seg in SEGMENTS:
        print(f"  → {seg['name']}")
        try:
            data = get_travel_time(api_key, seg["origin"], seg["destination"])
        except Exception as e:
            print(f"     ⚠️  Erreur Maps : {e}")
            data = {"status": f"ERROR: {e}"}

        row = [
            ts_utc, ts_local, seg["name"],
            data.get("duration_normal_s", ""),
            data.get("duration_traffic_s", ""),
            data.get("duration_normal_min", ""),
            data.get("duration_traffic_min", ""),
            data.get("delay_min", ""),
            data.get("distance_m", ""),
            data.get("distance_km", ""),
            data.get("traffic_ratio", ""),
            data.get("status", "ERROR"),
        ]
        rows_to_append.append(row)

        if data.get("status") == "OK":
            print(f"     ✓ {data['duration_traffic_min']} min "
                  f"(+{data['delay_min']} min, ratio {data['traffic_ratio']})")

    append_rows(sheet_id, token, rows_to_append)
    print(f"[{ts_utc}] ✅ {len(rows_to_append)} ligne(s) écrite(s) dans Sheets.")


if __name__ == "__main__":
    main()
