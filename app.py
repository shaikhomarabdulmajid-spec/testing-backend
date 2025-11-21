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
#   ANALYZE (fake AI model)
# --------------------------

@app.route("/analyze", methods=["POST"])
def analyze():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    decoded = decode_token(token)
    if not decoded:
        return jsonify({"success": False, "message": "Invalid token"})

    # The frontend sends form-data with an image file called "image"
    if "image" not in request.files:
        return jsonify({"success": False, "message": "No image uploaded"})

    img = request.files["image"]
    name = img.filename.lower()

    # Very simple fake model
    predicted_food = None
    for food in CALORIES:
        if food in name:
            predicted_food = food
            break

    if predicted_food is None:
        predicted_food = "unknown"

    calorie = CALORIES.get(predicted_food, 0)

    # Save in user history
    users.update_one(
        {"email": decoded["email"]},
        {"$push": {"history": {"food": predicted_food, "calories": calorie}}}
    )

    return jsonify({
        "success": True,
        "food": predicted_food,
        "calories": calorie
    })


# --------------------------
#   MAIN
# --------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
