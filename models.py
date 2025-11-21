# models.py
from pymongo import MongoClient
from bson.objectid import ObjectId
import os

MONGO_URI = os.environ.get("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client.get_default_database()
users = db.users

def create_user(username, hashed_password):
    try:
        users.insert_one({
            "username": username,
            "password": hashed_password,
            "foods": []
        })
        return True
    except Exception:
        return False

def find_user_by_username(username):
    return users.find_one({"username": username})

def find_user_by_id(uid):
    return users.find_one({"_id": ObjectId(uid)})

def add_foods_to_user(uid, foods):
    users.update_one({"_id": ObjectId(uid)}, {"$push": {"foods": {"$each": foods}}})
