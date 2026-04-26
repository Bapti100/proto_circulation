"""
collect.py — Collecte horaire du temps de trajet via Google Maps Distance Matrix API
Écrit les données dans Google Sheets via gspread.

Variables d'environnement requises (GitHub Secrets) :
  GMAPS_API_KEY  : clé API Google Maps
  GSHEET_ID      : ID du Google Spreadsheet cible

L'authentification Google Sheets est gérée automatiquement par Workload Identity
Federation via l'action google-github-actions/auth dans le workflow GitHub Actions.
"""

import os
import datetime
import requests
import gspread
import google.auth

SEGMENTS = [
    {
        "name": "Troncon_A_B",
        "origin": "Megeve, France",
        "destination": "Annecy, France",
    },
    {
        "name": "Troncon_A_C",
        "origin": "Megeve, France",
        "destination": "Sallanches, France",
    },
    # {
    #     "name": "Troncon_A_D",
    #     "origin": "Megeve, France",
    #     "destination": "Chamonix, France",
    # },
]

SHEET_NAME = "trafic_data"
HEADER = [
    "timestamp_utc", "timestamp_local", "segment",
    "duration_normal_s", "duration_traffic_s",
    "duration_normal_min", "duration_traffic_min",
    "delay_min", "distance_m", "distance_km",
    "traffic_ratio", "status",
]


def get_travel_time(api_key, origin, destination):
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": origin, "destinations": destination,
        "departure_time": "now", "traffic_model": "best_guess", "key": api_key,
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
        "duration_normal_s": dn, "duration_traffic_s": dt,
        "duration_normal_min": round(dn/60,1), "duration_traffic_min": round(dt/60,1),
        "delay_min": round((dt-dn)/60,1), "distance_m": dm,
        "distance_km": round(dm/1000,2), "traffic_ratio": round(dt/dn,3), "status": "OK",
    }


def get_sheet(sheet_id):
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds, _ = google.auth.default(scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(sheet_id)
    try:
        worksheet = spreadsheet.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=100, cols=20)
        worksheet.append_row(HEADER)
        print(f"Onglet '{SHEET_NAME}' créé.")
    if worksheet.row_count == 0 or worksheet.cell(1,1).value != HEADER[0]:
        worksheet.insert_row(HEADER, 1)
    return worksheet


def main():
    api_key  = os.environ["AIzaSyBzQM3l5GZtbWP-RcObDHODtQG3WJyOpig"]
    sheet_id = os.environ["1TtaK3bvo0n3QXAZoaBg-tSrXI6blZYLr82hRegFqTp0"]
    ts_utc   = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    ts_local = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts_utc}] Collecte en cours pour {len(SEGMENTS)} tronçon(s)...")
    worksheet = get_sheet(sheet_id)
    rows_to_append = []
    for seg in SEGMENTS:
        print(f"  → {seg['name']} : {seg['origin']} → {seg['destination']}")
        try:
            data = get_travel_time(api_key, seg["origin"], seg["destination"])
        except Exception as e:
            print(f"     ⚠️  Erreur : {e}")
            data = {k: "" for k in HEADER[4:]}
            data["status"] = f"ERROR: {e}"
        row = [ts_utc, ts_local, seg["name"],
               data.get("duration_normal_s",""), data.get("duration_traffic_s",""),
               data.get("duration_normal_min",""), data.get("duration_traffic_min",""),
               data.get("delay_min",""), data.get("distance_m",""),
               data.get("distance_km",""), data.get("traffic_ratio",""),
               data.get("status","ERROR")]
        rows_to_append.append(row)
        if data.get("status") == "OK":
            print(f"     ✓ {data['duration_traffic_min']} min (+{data['delay_min']} min, ratio {data['traffic_ratio']})")
    for row in rows_to_append:
        worksheet.append_row(row, value_input_option="USER_ENTERED")
    print(f"[{ts_utc}] ✅ {len(rows_to_append)} ligne(s) écrite(s).")

if __name__ == "__main__":
    main()
