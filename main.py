from flask import Flask, request, send_from_directory, jsonify, render_template
from datetime import datetime
import os, json, glob, time

app = Flask(__name__)

DATA_DIR = "tracks"
os.makedirs(DATA_DIR, exist_ok=True)
LIVE_FILE = os.path.join(DATA_DIR, "live.json")
LAST_FILE = os.path.join(DATA_DIR, "last_upload.json")

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

        # Record last upload timestamp
        with open(LAST_FILE, "w") as f:
            json.dump({"ts": time.time()}, f)

        return "OK"
    except Exception as e:
        return str(e), 500

# ---------------- Upload status ----------------
@app.route("/status")
def status():
    try:
        if not os.path.exists(LAST_FILE):
            return jsonify({"age_min": None, "next_min": None, "color": "red"})
        with open(LAST_FILE, "r") as f:
            t = json.load(f)["ts"]
        delta = time.time() - t
        age_min = int(delta / 60)
        next_min = max(0, 30 - age_min)
        color = "green"
        if age_min > 45:
            color = "orange"
        if age_min > 90:
            color = "red"
        return jsonify({
            "age_min": age_min,
            "next_min": next_min,
            "color": color
        })
    except Exception as e:
        return jsonify({"age_min": None, "next_min": None, "color": "red", "error": str(e)})

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
        if base in ("live.json", "last_upload.json"):
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
