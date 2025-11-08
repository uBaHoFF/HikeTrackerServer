# ============================================================
# HikeTracker Flask Server
# ============================================================

from flask import Flask, request, send_from_directory, jsonify, render_template
from datetime import datetime
import os, json, math, glob

app = Flask(__name__)

DATA_DIR = "tracks"
os.makedirs(DATA_DIR, exist_ok=True)
LIVE_FILE = os.path.join(DATA_DIR, "live.json")

# ----------------------------------------------------------------
# Helper: compute rough distance (to detect same trail overlaps)
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dLon/2)**2
    return 2*R*math.atan2(math.sqrt(a), math.sqrt(1-a))

# ----------------------------------------------------------------
# Endpoint: receive new GPS batches from Android app
@app.route("/upload", methods=["POST"])
def upload():
    try:
        data = request.get_json(force=True)
        pts = data.get("points", [])
        if not pts:
            return "no points", 400

        # Save live file
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

# ----------------------------------------------------------------
# Serve the map page
@app.route("/")
def map_page():
    return render_template("map.html")

# ----------------------------------------------------------------
# Serve all track JSONs (live + historical)
@app.route("/data")
def list_data():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
    result = []
    for f in files:
        base = os.path.basename(f)
        name = os.path.splitext(base)[0]
        try:
            with open(f, "r") as fh:
                js = json.load(fh)
                pts = js.get("points", [])
                if pts:
                    # Extract representative coords for overlap grouping
                    lat = sum(p["lat"] for p in pts) / len(pts)
                    lon = sum(p["lon"] for p in pts) / len(pts)
                    result.append({"file": base, "name": name, "lat": lat, "lon": lon})
        except Exception:
            continue
    return jsonify(result)

@app.route("/track/<path:fname>")
def get_track(fname):
    return send_from_directory(DATA_DIR, fname)

# ----------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
