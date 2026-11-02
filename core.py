"""Shared logic used by both the UI (main.py) and the background service (service.py)."""
import json
import os
import sqlite3
import time
from datetime import datetime

import requests


def data_dir():
    try:
        from android.storage import app_storage_path  # only exists on Android
        d = app_storage_path()
    except ImportError:
        d = os.path.join(os.path.expanduser("~"), ".faretracker")
    os.makedirs(d, exist_ok=True)
    return d


CFG = os.path.join(data_dir(), "config.json")
STATUS = os.path.join(data_dir(), "status.txt")
DB = os.path.join(data_dir(), "fares.db")


def load_cfg():
    try:
        with open(CFG) as f:
            return json.load(f)
    except Exception:
        return {}


def save_cfg(cfg):
    with open(CFG, "w") as f:
        json.dump(cfg, f)


def set_status(text):
    with open(STATUS, "w") as f:
        f.write(f"[{datetime.now():%b %d %H:%M}] {text}")


def get_status():
    try:
        with open(STATUS) as f:
            return f.read()
    except Exception:
        return "Not started."


def db():
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS fares "
                "(ts TEXT, route TEXT, price REAL, airlines TEXT, stops INT)")
    return con


def history(limit=10):
    con = db()
    rows = con.execute("SELECT ts, route, price, airlines, stops FROM fares "
                       "ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    con.close()
    return rows


def base_url(cfg):
    return ("https://api.amadeus.com" if cfg.get("env") == "production"
            else "https://test.api.amadeus.com")


def get_token(cfg):
    r = requests.post(
        f"{base_url(cfg)}/v1/security/oauth2/token",
        data={"grant_type": "client_credentials",
              "client_id": cfg["key"], "client_secret": cfg["secret"]},
        timeout=20)
    r.raise_for_status()
    return r.json()["access_token"]


def search_fares(cfg, token):
    params = {
        "originLocationCode": cfg["origin"].upper(),
        "destinationLocationCode": cfg["dest"].upper(),
        "departureDate": cfg["depart"],
        "adults": int(cfg.get("adults") or 1),
        "currencyCode": cfg.get("currency") or "USD",
        "max": 20,
    }
    if cfg.get("ret"):
        params["returnDate"] = cfg["ret"]
    r = requests.get(f"{base_url(cfg)}/v2/shopping/flight-offers",
                     headers={"Authorization": f"Bearer {token}"},
                     params=params, timeout=30)
    r.raise_for_status()
    offers = r.json().get("data", [])
    if not offers:
        return None
    best = min(offers, key=lambda o: float(o["price"]["total"]))
    segs = best["itineraries"][0]["segments"]
    return {"price": float(best["price"]["total"]),
            "airlines": ",".join(sorted({s["carrierCode"] for s in segs})),
            "stops": len(segs) - 1}


def notify(cfg, title, msg):
    try:
        from plyer import notification
        notification.notify(title=title, message=msg, timeout=10)
    except Exception:
        pass
    topic = cfg.get("ntfy")
    if topic:
        try:
            requests.post(f"https://ntfy.sh/{topic}", data=msg.encode(), timeout=10)
        except requests.RequestException:
            pass


_token = {"value": None, "time": 0}


def run_check(cfg):
    """Do one price check; store it; fire alerts. Returns a status string."""
    route = f"{cfg['origin'].upper()}-{cfg['dest'].upper()} {cfg['depart']}"
    if cfg.get("ret"):
        route += f" / {cfg['ret']}"
    try:
        if not _token["value"] or time.time() - _token["time"] > 1500:
            _token["value"], _token["time"] = get_token(cfg), time.time()
        fare = search_fares(cfg, _token["value"])
    except requests.HTTPError as e:
        _token["value"] = None
        return f"API error {e.response.status_code}: {e.response.text[:120]}"
    except Exception as e:
        return f"Error: {e}"

    if fare is None:
        return f"No offers found for {route}"

    con = db()
    prev_low = con.execute("SELECT MIN(price) FROM fares WHERE route=?", (route,)).fetchone()[0]
    con.execute("INSERT INTO fares VALUES (?,?,?,?,?)",
                (datetime.now().isoformat(), route, fare["price"], fare["airlines"], fare["stops"]))
    con.commit()
    con.close()

    cur = cfg.get("currency") or "USD"
    line = f"{route}: {cur} {fare['price']:.2f} ({fare['airlines']}, {fare['stops']} stops)"
    target = cfg.get("target")
    try:
        target = float(target) if target else None
    except ValueError:
        target = None

    if target and fare["price"] <= target:
        notify(cfg, "Fare at your target!", line)
    elif prev_low is not None and fare["price"] < prev_low:
        notify(cfg, "New low fare", f"{line} (was {prev_low:.2f})")
    return line
