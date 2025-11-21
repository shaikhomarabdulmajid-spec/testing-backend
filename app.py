import datetime
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import os

from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
CORS(app)

# Ensure uploads folder exists
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Dummy in-memory "database" for login/register
USERS = {}  # username -> password
USER_HISTORY = {}  # username -> list of foods

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
    # Check image
    if "image" not in request.files:
        return jsonify({"success": False, "message": "No image uploaded"}), 400

    image = request.files["image"]
    if image.filename == "":
        return jsonify({"success": False, "message": "No file selected"}), 400

    # Save image temporarily
    img_path = os.path.join(UPLOAD_FOLDER, image.filename)
    image.save(img_path)

    # Dummy AI analysis (replace with real model later)
    detected_foods = [
        {"name": "Sandwich", "calories": 350},
        {"name": "Apple", "calories": 95}
    ]
    total_calories = sum(f["calories"] for f in detected_foods)

    # Save to user history if username provided in headers
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
