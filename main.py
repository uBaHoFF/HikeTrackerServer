from flask import Flask, request, send_from_directory, jsonify, render_template
from datetime import datetime
import os, json, glob, time

app = Flask(__name__)

DATA_DIR = "tracks"
os.makedirs(DATA_DIR, exist_ok=True)
LIVE_FILE = os.path.join(DATA_DIR, "live.json")
LAST_FILE = os.path.join(DATA_DIR, "last_upload.json")

# ---------------- Upload points (with ACK) ----------------
@app.route("/upload", methods=["POST"])
def upload():
    try:
        # Safe JSON parsing
        data = request.get_json(force=True, silent=True)
        if not data or "points" not in data:
            return jsonify({"error": "invalid"}), 400

        pts = data["points"]
        batch_id = data.get("batch_id", data.get("batch", -1))

        if not isinstance(pts, list) or not pts:
            return jsonify({"error": "no points"}), 400

        # Safety limit to protect Render RAM
        if len(pts) > 1000:
            return jsonify({"error": "too many points"}), 413

        # ---- Save live file (recent 200 points only) ----
        with open(LIVE_FILE, "w") as f:
            json.dump({"points": pts[-200:]}, f)

        # ---- Append to daily archive ----
        today = datetime.utcnow().strftime("%d_%m_%Y")
        fpath = os.path.join(DATA_DIR, f"{today}.json")

        existing = []
        if os.path.exists(fpath):
            try:
                with open(fpath, "r") as f:
                    existing = json.load(f).get("points", [])
            except Exception:
                existing = []

        existing.extend(pts)

        # Optional cap to prevent massive files
        if len(existing) > 100000:
            existing = existing[-100000:]

        with open(fpath, "w") as f:
            json.dump({"points": existing}, f)

        # ---- Record last upload timestamp ----
        with open(LAST_FILE, "w") as f:
            json.dump({"ts": time.time()}, f)

        # ---- IMPORTANT: Server ACK back to app ----
        return jsonify({
            "status": "ok",
            "ack_batch": batch_id,
            "received": len(pts)
        }), 200

    except Exception as e:
        print("Upload exception:", e)
        return jsonify({"error": str(e)}), 500


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
        return jsonify({
            "age_min": None, "next_min": None,
            "color": "red", "error": str(e)
        })

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
                    result.append({
                        "file": base,
                        "name": name,
                        "lat": lat,
                        "lon": lon
                    })
        except Exception:
            continue
    return jsonify(result)

@app.route("/track/<path:fname>")
def get_track(fname):
    return send_from_directory(DATA_DIR, fname)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)


