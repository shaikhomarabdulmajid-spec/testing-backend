from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import os
import json
import datetime
import requests

# -------------------------
# Load env vars
# -------------------------
from dotenv import load_dotenv
load_dotenv()

MONGO_URI = os.environ.get("MONGO_URI")
HF_API_KEY = os.environ.get("HF_API_KEY")

# -------------------------
# Flask setup
# -------------------------
app = Flask(__name__)
CORS(app)

# -------------------------
# MongoDB setup
# -------------------------
client = MongoClient(MONGO_URI)
db = client["food_app"]
users_col = db["users"]
history_col = db["history"]

# -------------------------
# Load local calorie DB
# -------------------------
with open("calorie_db.json", "r") as f:
    calorie_db = json.load(f)

# -------------------------
# Routes
# -------------------------

## --- REGISTER ---
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if users_col.find_one({"username": username}):
        return jsonify({"success": False, "message": "Username already exists"})

    users_col.insert_one({"username": username, "password": password})
    return jsonify({"success": True})

## --- LOGIN ---
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    user = users_col.find_one({"username": username})
    if not user or user["password"] != password:
        return jsonify({"success": False, "message": "Invalid credentials"})

    return jsonify({"success": True})

## --- GET HISTORY (optional) ---
@app.route("/history", methods=["GET"])
def get_history():
    username = request.args.get("username", "guest")  # frontend can pass username
    records = list(history_col.find({"username": username}, {"_id": 0}))
    return jsonify({"success": True, "history": records})

## --- ANALYZE IMAGE ---
@app.route("/analyze", methods=["POST"])
def analyze():
    username = request.form.get("username", "guest")  # optional from frontend

    if "image" not in request.files:
        return jsonify({"success": False, "message": "No image uploaded"})
    
    image_file = request.files["image"]

    # Send to HuggingFace Inference API
    HF_URL = "https://api-inference.huggingface.co/models/nateraw/food-classifier"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    response = requests.post(HF_URL, headers=headers, files={"file": image_file.read()})
    
    if response.status_code != 200:
        return jsonify({"success": False, "message": "AI model error"})

    predictions = response.json()
    top_prediction = predictions[0]["label"].lower()
    calories = calorie_db.get(top_prediction, 0)
    steps_needed = calories * 20

    # Save record in DB
    history_col.insert_one({
        "username": username,
        "food": top_prediction,
        "calories": calories,
        "timestamp": datetime.datetime.utcnow().isoformat()
    })

    return jsonify({
        "success": True,
        "food": top_prediction,
        "calories": calories,
        "steps": steps_needed
    })

# -------------------------
# Run Flask
# -------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
