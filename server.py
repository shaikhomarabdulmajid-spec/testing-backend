import os
import io
import json
import bcrypt
import jwt
import requests
from datetime import datetime, timedelta
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from models import create_user, find_user_by_username, find_user_by_id, add_foods_to_user

load_dotenv()

app = Flask(__name__)
CORS(app)

JWT_SECRET = os.environ.get("JWT_SECRET", "replace_this")
JWT_ALGO = "HS256"

CLARIFAI_API_KEY = os.environ.get("CLARIFAI_API_KEY")
NUTRITIONIX_APP_ID = os.environ.get("NUTRITIONIX_APP_ID")
NUTRITIONIX_API_KEY = os.environ.get("NUTRITIONIX_API_KEY")

# Simple fallback calorie map (per typical serving)
FALLBACK_CALORIES = {
    "pizza": 285,
    "burger": 550,
    "fries": 300,
    "apple": 95,
    "banana": 105,
    "egg": 78,
    "salad": 150,
    "rice": 206,
    "chicken": 239
}


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if "Authorization" in request.headers:
            token = request.headers["Authorization"]
        if not token:
            return jsonify({"success": False, "message": "Token is missing"}), 401
        try:
            data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
            request.user_id = data["id"]
        except Exception:
            return jsonify({"success": False, "message": "Token invalid"}), 401
        return f(*args, **kwargs)
    return decorated


@app.route("/register", methods=["POST"])
def register():
    body = request.get_json()
    username = body.get("username") or body.get("email")
    password = body.get("password")
    if not username or not password:
        return jsonify({"success": False, "message": "username & password required"})
    if find_user_by_username(username):
        return jsonify({"success": False, "message": "User exists"})
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    ok = create_user(username, hashed)
    if ok:
        return jsonify({"success": True, "message": "Registered"})
    return jsonify({"success": False, "message": "Register failed"})


@app.route("/login", methods=["POST"])
def login():
    body = request.get_json()
    username = body.get("username") or body.get("email")
    password = body.get("password")
    if not username or not password:
        return jsonify({"success": False, "message": "Provide username & password"})
    user = find_user_by_username(username)
    if not user:
        return jsonify({"success": False, "message": "User not found"})
    if not bcrypt.checkpw(password.encode(), user["password"].encode()):
        return jsonify({"success": False, "message": "Wrong password"})
    token = jwt.encode({
        "id": str(user["_id"]),
        "exp": datetime.utcnow() + timedelta(days=7)
    }, JWT_SECRET, algorithm=JWT_ALGO)
    return jsonify({"success": True, "token": token})


def clarifai_predict_food(image_bytes):
    """
    Uses Clarifai's Food model to return a list of predicted food names (strings).
    Requires CLARIFAI_API_KEY in env.
    """
    if not CLARIFAI_API_KEY:
        return []

    url = "https://api.clarifai.com/v2/models/food-item-recognition/outputs"
    headers = {
        "Authorization": f"Key {CLARIFAI_API_KEY}",
        "Content-Type": "application/json"
    }
    # Clarifai expects base64 image inside JSON or URL; use base64
    import base64
    b64 = base64.b64encode(image_bytes).decode()
    payload = {
        "inputs": [
            {
                "data": {
                    "image": {
                        "base64": b64
                    }
                }
            }
        ]
    }
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    if r.status_code != 200:
        return []
    try:
        outputs = r.json().get("outputs", [])
        concepts = outputs[0]["data"].get("concepts", [])
        # return top 5 names
        return [c["name"] for c in concepts[:6]]
    except Exception:
        return []


def nutritionix_lookup(query_text):
    """
    Use Nutritionix natural language endpoint to parse calories for a query like '1 slice pizza'.
    Returns calories (float) or None.
    """
    if not (NUTRITIONIX_APP_ID and NUTRITIONIX_API_KEY):
        return None
    url = "https://trackapi.nutritionix.com/v2/natural/nutrients"
    headers = {
        "x-app-id": NUTRITIONIX_APP_ID,
        "x-app-key": NUTRITIONIX_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {"query": query_text}
    r = requests.post(url, headers=headers, json=payload, timeout=8)
    if r.status_code != 200:
        return None
    try:
        foods = r.json().get("foods", [])
        if not foods:
            return None
        # return calories from first item
        return foods[0].get("nf_calories")
    except Exception:
        return None


@app.route("/analyze", methods=["POST"])
def analyze():
    # Accept file field named "image" (this matches your frontend)
    if "image" not in request.files:
        return jsonify({"success": False, "message": "No image sent"}), 400

    file = request.files["image"]
    img_bytes = file.read()

    # 1) Get food labels from Clarifai
    labels = clarifai_predict_food(img_bytes)
    if not labels:
        # fallback: attempt to decode filename or use a generic fallback
        labels = ["food"]

    foods = []
    total = 0

    # For each label, try Nutritionix lookup (e.g. "1 serving pizza")
    for label in labels:
        # build a short query; Nutritionix tends to work with "1 serving *label*"
        q = f"1 serving {label}"
        cal = nutritionix_lookup(q)
        if cal is None:
            # fallback to local mapping using lowercase containment
            label_lower = label.lower()
            found = None
            for key, val in FALLBACK_CALORIES.items():
                if key in label_lower:
                    found = val
                    break
            cal = found or 200  # default guess if nothing found
        foods.append({"name": label, "calories": round(cal)})
        total += cal

    # Save to user history if Authorization token provided
    token = request.headers.get("Authorization")
    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
            uid = payload["id"]
            # construct items with timestamp
            to_save = []
            for f in foods:
                to_save.append({
                    "name": f["name"],
                    "calories": int(round(f["calories"])),
                    "date": datetime.utcnow()
                })
            add_foods_to_user(uid, to_save)
        except Exception:
            pass  # ignore token errors for analysis result

    return jsonify({
        "success": True,
        "foods": foods,
        "total_calories": int(round(total))
    })


@app.route("/history", methods=["GET"])
@token_required
def history():
    user = find_user_by_id(request.user_id)
    if not user:
        return jsonify({"success": False, "message": "No user"}), 404
    foods = user.get("foods", [])
    # format: name, calories, date (ISO)
    out = [{
        "name": f.get("name"),
        "calories": f.get("calories"),
        "date": f.get("date").isoformat() if f.get("date") else None
    } for f in foods]
    return jsonify({"success": True, "history": out})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
