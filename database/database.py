"""
Database engine using Firebase Firestore for persistent cloud storage.
Replaces SQLAlchemy/SQLite to survive Render redeployments.
"""
import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from auth.auth import get_password_hash
from datetime import datetime

# ── Firebase Initialization ─────────────────────────────────────────
_firebase_app = None
_firestore_client = None

def _init_firebase():
    """Initialize Firebase Admin SDK (called once)."""
    global _firebase_app, _firestore_client
    if _firebase_app is not None:
        return

    # Option 1: Environment variable (for Render deployment) — checked FIRST
    env_creds = os.environ.get("FIREBASE_CREDENTIALS")

    # Option 2: JSON key file in project root (local development fallback)
    key_path = os.path.join(os.path.dirname(__file__), "..", "firebase_key.json")

    if env_creds:
        cred_dict = json.loads(env_creds)
        cred = credentials.Certificate(cred_dict)
    elif os.path.exists(key_path):
        cred = credentials.Certificate(key_path)
    else:
        raise RuntimeError(
            "Firebase credentials not found. "
            "Place firebase_key.json in project root or set FIREBASE_CREDENTIALS env var."
        )

    _firebase_app = firebase_admin.initialize_app(cred)
    import google.cloud.firestore
    _firestore_client = google.cloud.firestore.Client(
        project=_firebase_app.project_id,
        database='crs-systemm',
        credentials=cred.get_credential()
    )
    print("[FIREBASE] Connected to Firestore successfully")


def get_db():
    """FastAPI dependency — yields a Firestore client."""
    _init_firebase()
    yield _firestore_client


def get_firestore_client():
    """Direct access to Firestore client (non-dependency use)."""
    _init_firebase()
    return _firestore_client


# ── Auto-increment ID helper ────────────────────────────────────────
def _next_id(collection_name: str) -> int:
    """Generate auto-incrementing integer IDs using Firestore transactions."""
    db = get_firestore_client()
    counter_ref = db.collection("_counters").document(collection_name)

    @firestore.transactional
    def _increment(transaction):
        snapshot = counter_ref.get(transaction=transaction)
        if snapshot.exists:
            current = snapshot.to_dict().get("next_id", 1)
        else:
            # Counter missing: scan collection to find the real max ID
            max_id = 0
            for doc in db.collection(collection_name).select(["id"]).stream():
                doc_id = doc.to_dict().get("id", 0)
                if isinstance(doc_id, int) and doc_id > max_id:
                    max_id = doc_id
            current = max_id + 1
        transaction.set(counter_ref, {"next_id": current + 1})
        return current

    transaction = db.transaction()
    return _increment(transaction)


# ── Seeding ──────────────────────────────────────────────────────────
def init_db():
    """Seed default data into Firestore ONLY on the very first run."""
    _init_firebase()
    db = _firestore_client

    # Permanent seed flag — once set, seeding NEVER runs again
    seed_flag = db.collection("_counters").document("_seed_done").get()
    if seed_flag.exists:
        print("[FIREBASE] Seed already completed previously, skipping")
        return

    # Extra safety: check if any data exists in any collection
    for coll_name in ["officers", "persons", "criminal_records"]:
        existing = list(db.collection(coll_name).limit(1).stream())
        if existing:
            print(f"[FIREBASE] Data found in '{coll_name}', marking seed as done and skipping")
            db.collection("_counters").document("_seed_done").set({"done": True})
            return

    print("[FIREBASE] Seeding initial data...")

    # ── Seed Officers ──
    officer_data = [
        {
            "username": "officer_rakesh",
            "full_name": "Snr. Inspector Rakesh Sharma",
            "hashed_password": get_password_hash("Rakesh@001"),
            "role": "admin",
            "badge_number": "KOL-001",
            "department": "Criminal Investigation",
            "is_active": 1,
            "created_at": datetime.utcnow().isoformat(),
        },
        {
            "username": "officer_priya",
            "full_name": "Sub-Inspector Priya Menon",
            "hashed_password": get_password_hash("Priya@002"),
            "role": "officer",
            "badge_number": "KOL-002",
            "department": "Criminal Investigation",
            "is_active": 1,
            "created_at": datetime.utcnow().isoformat(),
        },
        {
            "username": "officer_arjun",
            "full_name": "Constable Arjun Das",
            "hashed_password": get_password_hash("Arjun@003"),
            "role": "viewer",
            "badge_number": "KOL-003",
            "department": "Field Operations",
            "is_active": 1,
            "created_at": datetime.utcnow().isoformat(),
        },
    ]

    for odata in officer_data:
        oid = _next_id("officers")
        odata["id"] = oid
        officers_ref.document(str(oid)).set(odata)
    print(f"[FIREBASE] Seeded {len(officer_data)} officers")

    # ── Seed Sample Persons ──
    samples = [
        {
            "full_name": "Marcus Johnson",
            "date_of_birth": "1985-03-15",
            "gender": "Male",
            "nationality": "American",
            "address": "1425 Oak Street, Chicago, IL",
            "government_id_number": "SSN-XXX-XX-4521",
            "record_status": "Convicted",
            "risk_level": "High",
            "face_embedding_encrypted": None,
            "image_path": None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "crimes": [
                {
                    "crime_type": "Armed Robbery",
                    "crime_description": "Armed robbery of First National Bank, downtown branch",
                    "case_number": "CR-2023-04521",
                    "date_of_offense": "2023-06-12",
                    "arrest_date": "2023-06-14",
                    "conviction_status": "Convicted",
                    "sentence_details": "15 years federal prison",
                    "law_enforcement_agency": "FBI",
                    "court_name": "US District Court, Northern Illinois",
                },
                {
                    "crime_type": "Assault",
                    "crime_description": "Aggravated assault during arrest attempt",
                    "case_number": "CR-2023-04522",
                    "date_of_offense": "2023-06-14",
                    "arrest_date": "2023-06-14",
                    "conviction_status": "Convicted",
                    "sentence_details": "5 years (concurrent)",
                    "law_enforcement_agency": "Chicago PD",
                    "court_name": "Cook County Criminal Court",
                },
            ],
        },
        {
            "full_name": "Elena Vasquez",
            "date_of_birth": "1990-11-22",
            "gender": "Female",
            "nationality": "Mexican-American",
            "address": "2900 Sunset Blvd, Los Angeles, CA",
            "government_id_number": "SSN-XXX-XX-7833",
            "record_status": "Under Investigation",
            "risk_level": "Medium",
            "face_embedding_encrypted": None,
            "image_path": None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "crimes": [
                {
                    "crime_type": "Wire Fraud",
                    "crime_description": "Multi-state wire fraud scheme totaling $2.3M",
                    "case_number": "CR-2024-00891",
                    "date_of_offense": "2024-01-05",
                    "arrest_date": "2024-02-20",
                    "conviction_status": "Pending Trial",
                    "sentence_details": "Awaiting sentencing",
                    "law_enforcement_agency": "Secret Service",
                    "court_name": "US District Court, Central California",
                },
            ],
        },
        {
            "full_name": "David Kim",
            "date_of_birth": "1978-07-09",
            "gender": "Male",
            "nationality": "Korean-American",
            "address": "550 Pine Ave, Seattle, WA",
            "government_id_number": "SSN-XXX-XX-2198",
            "record_status": "Released",
            "risk_level": "Low",
            "face_embedding_encrypted": None,
            "image_path": None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "crimes": [
                {
                    "crime_type": "Tax Evasion",
                    "crime_description": "Failure to report $500K in offshore income",
                    "case_number": "CR-2020-11234",
                    "date_of_offense": "2019-04-15",
                    "arrest_date": "2020-03-10",
                    "conviction_status": "Convicted",
                    "sentence_details": "2 years (served), 3 years probation",
                    "law_enforcement_agency": "IRS Criminal Investigation",
                    "court_name": "US District Court, Western Washington",
                },
            ],
        },
    ]

    persons_ref = db.collection("persons")
    records_ref = db.collection("criminal_records")

    for s in samples:
        crimes = s.pop("crimes")
        pid = _next_id("persons")
        s["id"] = pid
        persons_ref.document(str(pid)).set(s)

        for c in crimes:
            rid = _next_id("criminal_records")
            c["id"] = rid
            c["person_id"] = pid
            c["last_updated"] = datetime.utcnow().isoformat()
            records_ref.document(str(rid)).set(c)

    print(f"[FIREBASE] Seeded {len(samples)} persons with criminal records")

    # Mark seeding as permanently done
    db.collection("_counters").document("_seed_done").set({"done": True})
    print("[FIREBASE] Seed flag set — seeding will not run again")
