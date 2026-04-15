import firebase_admin
from firebase_admin import credentials, firestore

# --- Initialization ---
if not firebase_admin._apps:
    cred = credentials.Certificate("credentials.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()