"""
Data models and Enums for the Criminal Recognition System.
Adapted for Firebase Firestore (removed SQLAlchemy).
"""
import enum

# ── Enums ──────────────────────────────────────────────────────────────
class RecordStatus(str, enum.Enum):
    CLEAN = "Clean"
    UNDER_INVESTIGATION = "Under Investigation"
    CONVICTED = "Convicted"
    RELEASED = "Released"

class RiskLevel(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"

class ActionType(str, enum.Enum):
    SEARCH = "Search"
    ADD = "Add"
    UPDATE = "Update"
    DELETE = "Delete"
    LOGIN = "Login"

class OfficerRole(str, enum.Enum):
    ADMIN = "admin"
    OFFICER = "officer"
    VIEWER = "viewer"

# Data representations in Firestore are dictionaries.
# The keys used in the collections:

# ── Officers (Users) ──────────────────────────────────────────────────
# id: int
# username: str
# full_name: str
# hashed_password: str
# role: str
# badge_number: str
# department: str
# is_active: int
# created_at: str (isoformat)

# ── Persons ───────────────────────────────────────────────────────────
# id: int
# full_name: str
# date_of_birth: str
# gender: str
# nationality: str
# address: str
# government_id_number: str
# face_embedding_encrypted: str
# image_path: str
# record_status: str
# risk_level: str
# created_at: str (isoformat)
# updated_at: str (isoformat)

# ── Criminal Records ─────────────────────────────────────────────────
# id: int
# person_id: int
# crime_type: str
# crime_description: str
# case_number: str
# date_of_offense: str
# arrest_date: str
# conviction_status: str
# sentence_details: str
# law_enforcement_agency: str
# court_name: str
# officer_notes: str
# last_updated: str (isoformat)

# ── Audit Log ─────────────────────────────────────────────────────────
# id: int
# officer_id: int
# action_type: str
# timestamp: str (isoformat)
# person_id: int (optional)
# details: str
# ip_address: str
