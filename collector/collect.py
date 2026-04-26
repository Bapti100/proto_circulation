"""
collect.py — Collecte horaire du temps de trajet via Google Maps Distance Matrix API
Écrit les données dans Google Sheets via l'API REST.
"""

import os
import datetime
import requests
import google.auth
import google.auth.transport.requests

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


def get_token():
    """Obtient un token OAuth2 via Application Default Credentials (WIF)."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds, _ = google.auth.default(scopes=scopes)
    auth_req = google.auth.transport.requests.Request()
    creds.refresh(auth_req)
    print(f"✓ Token obtenu, type: {type(creds).__name__}")
    return creds.token


def sheets_request(method, path, token, body=None):
    """Appelle l'API Google Sheets REST."""
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = requests.request(method, url, headers=headers, json=body, timeout=15)
    resp.raise_for_status()
    return resp.json() if resp.text else {}


def ensure_sheet_header(sheet_id, token):
    """Vérifie que l'onglet a les bons en-têtes."""
    try:
        data = sheets_request("GET", f"{sheet_id}/values/{SHEET_NAME}!A1:L1", token)
        values = data.get("values", [])
        if values and values[0] == HEADER:
            return
    except Exception:
        pass
    try:
        body = {"values": [HEADER]}
        sheets_request("PUT",
            f"{sheet_id}/values/{SHEET_NAME}!A1:L1?valueInputOption=USER_ENTERED",
            token, body)
        print(f"En-têtes écrits dans '{SHEET_NAME}'.")
    except Exception as e:
        print(f"Note: impossible d'écrire les en-têtes : {e}")


def append_rows(sheet_id, token, rows):
    """Ajoute des lignes à la suite du sheet."""
    body = {"values": rows}
    result = sheets_request(
        "POST",
        f"{sheet_id}/values/{SHEET_NAME}:append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS",
        token,
        body,
    )
    return result


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
    ts_local = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"[{ts_utc}] Collecte en cours pour {len(SEGMENTS)} tronçon(s)...")

    token = get_token()
    ensure_sheet_header(sheet_id, token)

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
