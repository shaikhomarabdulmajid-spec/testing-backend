from flask_cors import CORS
CORS(app)

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import json
import os


from database import users

from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "defaultsecret")

@app.route("/")
def home():
    return "Backend is running!"


# Load calorie DB
with open("calorie_db.json", "r") as f:
    CALORIES = json.load(f)


# --------------------------
# Helper: Token
# --------------------------

def create_token(email):
    return jwt.encode(
        {"email": email, "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=10)},
        app.config['SECRET_KEY'],
        algorithm="HS256"
    )


def decode_token(token):
    try:
        return jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
    except:
        return None


# --------------------------
#   REGISTER
# --------------------------

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if users.find_one({"email": email}):
        return jsonify({"success": False, "message": "Email already exists."})

    hashed = generate_password_hash(password)

    users.insert_one({
        "email": email,
        "password": hashed,
        "history": []
    })

    return jsonify({"success": True, "message": "Registered successfully."})


# --------------------------
#   LOGIN
# --------------------------

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    user = users.find_one({"email": email})
    if not user:
        return jsonify({"success": False, "message": "User not found."})

    if not check_password_hash(user["password"], password):
        return jsonify({"success": False, "message": "Incorrect password."})

    token = create_token(email)
    return jsonify({"success": True, "token": token})


# --------------------------
#   GET HISTORY
# --------------------------

@app.route("/history", methods=["GET"])
def history():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    decoded = decode_token(token)
    if not decoded:
        return jsonify({"success": False, "message": "Invalid token"})

    user = users.find_one({"email": decoded["email"]})
    return jsonify({"success": True, "history": user.get("history", [])})


# --------------------------
#   ANALYZE
# --------------------------

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        # Check file uploaded
        if "image" not in request.files:
            return jsonify({"success": False, "message": "No file uploaded"}), 400

        image = request.files["image"]

        if image.filename == "":
            return jsonify({"success": False, "message": "No file selected"}), 400

        # Save image temporarily
        img_path = os.path.join("uploads", image.filename)
        image.save(img_path)

        # Fake model output (replace later if needed)
        detected_food = "Sandwich"
        calories = 350
        steps = 4500

        # Return EXACT format that your frontend expects
        return jsonify({
            "success": True,
            "food": detected_food,
            "calories": calories,
            "steps": steps
        })

    except Exception as e:
        print("ANALYZE ERROR:", e)
        return jsonify({"success": False, "message": "Server error"}), 500


# --------------------------
#   MAIN
# --------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
