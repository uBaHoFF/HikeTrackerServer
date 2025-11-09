from flask import Flask, request, send_from_directory, jsonify, render_template
from datetime import datetime
import os, json, math, glob, time

app = Flask(__name__)

DATA_DIR = "tracks"
os.makedirs(DATA_DIR, exist_ok=True)
LIVE_FILE = os.path.join(DATA_DIR, "live.json")
PING_FILE = os.path.join(DATA_DIR, "ping.json")

# ---------------- Haversine (unused here but kept) ----------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0
    import math as m
    dLat = m.radians(lat2 - lat1)
    dLon = m.radians(lon2 - lon1)
    a = m.sin(dLat/2)**2 + m.cos(m.radians(lat1))*m.cos(m.radians(lat2))*m.sin(dLon/2)**2
    return 2*R*m.atan2(m.sqrt(a), m.sqrt(1-a))

# ---------------- Upload points ----------------
@app.route("/upload", methods=["POST"])
def upload():
    try:
        data = request.get_json(force=True)
        pts = data.get("points", [])
        if not pts:
            return "no points", 400

        # Save live for map
        with open(LIVE_FILE, "w") as f:
            json.dump({"points": pts}, f)

        # Append to today's archive
        today = datetime.utcnow().strftime("%d_%m_%Y")
        fpath = os.path.join(DATA_DIR, f"{today}.json")
        if os.path.exists(fpath):
            with open(fpath, "r") as f:
                existing = json.load(f).get("points", [])
        else:
            existing = []
        existing.extend(pts)
        with open(fpath, "w") as f:
            json.dump({"points": existing}, f)

        return "OK"
    except Exception as e:
        return str(e), 500

# ---------------- Heartbeat ----------------
@app.route("/ping", methods=["POST"])
def ping():
    try:
        with open(PING_FILE, "w") as f:
            json.dump({"ts": time.time()}, f)
        return "OK"
    except Exception as e:
        return str(e), 500

@app.route("/ping/status")
def ping_status():
    try:
        if not os.path.exists(PING_FILE):
            return jsonify({"alive": False, "since": None})
        with open(PING_FILE, "r") as f:
            t = json.load(f)["ts"]
        delta = time.time() - t
        return jsonify({"alive": delta < 300, "since": int(delta)})  # 5 minutes
    except Exception:
        return jsonify({"alive": False, "since": None})

# ---------------- Map & data ----------------
@app.route("/")
def map_page():
    return render_template("map.html")

@app.route("/data")
def list_data():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
    result = []
    for f in files:
        base = os.path.basename(f)
        if base == "live.json" or base == "ping.json":
            continue
        name = os.path.splitext(base)[0]
        try:
            with open(f, "r") as fh:
                js = json.load(fh)
                pts = js.get("points", [])
                if pts:
                    lat = sum(p["lat"] for p in pts) / len(pts)
                    lon = sum(p["lon"] for p in pts) / len(pts)
                    result.append({"file": base, "name": name, "lat": lat, "lon": lon})
        except Exception:
            continue
    return jsonify(result)

@app.route("/track/<path:fname>")
def get_track(fname):
    return send_from_directory(DATA_DIR, fname)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
