from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from PIL import Image
import requests
from io import BytesIO
import json

app = Flask(__name__)
CORS(app)

# Ensure uploads folder exists
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Dummy in-memory users/history
USERS = {}
USER_HISTORY = {}

# Hugging Face API
HF_API_KEY = os.getenv("HF_API_KEY")
HF_MODEL = "google/vit-base-patch16-224"  # example, can replace with a food-specific model
HF_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
HEADERS = {"Authorization": f"Bearer {HF_API_KEY}"}

@app.route("/")
def home():
    return "Backend is running!"

# ---------------- LOGIN ----------------
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    if username in USERS and USERS[username] == password:
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Invalid credentials"})

# ---------------- REGISTER ----------------
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    if username in USERS:
        return jsonify({"success": False, "message": "User already exists"})
    USERS[username] = password
    USER_HISTORY[username] = []
    return jsonify({"success": True})

# ---------------- ANALYZE ----------------
@app.route("/analyze", methods=["POST"])
def analyze():
    if "image" not in request.files:
        return jsonify({"success": False, "message": "No image uploaded"}), 400

    image = request.files["image"]
    if image.filename == "":
        return jsonify({"success": False, "message": "No file selected"}), 400

    # Save image temporarily
    img_path = os.path.join(UPLOAD_FOLDER, image.filename)
    image.save(img_path)

    # ---------------- Hugging Face API call ----------------
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    response = requests.post(
        HF_URL,
        headers=HEADERS,
        files={"file": img_bytes}
    )

    if response.status_code != 200:
        return jsonify({"success": False, "message": "Error from AI model"}), 500

    predictions = response.json()

    # Extract top 2 predicted foods (example)
    detected_foods = []
    for pred in predictions[:2]:
        name = pred.get("label", "Unknown")
        calories = 100  # placeholder, you can implement real calorie lookup later
        detected_foods.append({"name": name, "calories": calories})

    total_calories = sum(f["calories"] for f in detected_foods)

    # Save to user history
    username = request.headers.get("username")
    if username and username in USER_HISTORY:
        USER_HISTORY[username].extend(detected_foods)

    return jsonify({
        "success": True,
        "foods": detected_foods,
        "total_calories": total_calories
    })

# ---------------- GET HISTORY ----------------
@app.route("/history", methods=["GET"])
def history():
    username = request.args.get("username")
    if not username or username not in USER_HISTORY:
        return jsonify({"success": False, "message": "No history"})
    return jsonify({"success": True, "history": USER_HISTORY[username]})

if __name__ == "__main__":
    app.run(debug=True)
