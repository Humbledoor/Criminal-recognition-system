"""
Database engine, session management, and seeding.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, Officer, Person, CriminalRecord
from auth.auth import get_password_hash

DATABASE_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DATABASE_URL = f"sqlite:///{os.path.join(DATABASE_DIR, 'criminal_recognition.db')}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency -- yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create tables and seed default data."""
    os.makedirs(DATABASE_DIR, exist_ok=True)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Seed default officers if none exist (matches frontend login credentials)
        if not db.query(Officer).first():
            officer_rakesh = Officer(
                username="officer_rakesh",
                full_name="Snr. Inspector Rakesh Sharma",
                hashed_password=get_password_hash("Rakesh@001"),
                role="admin",
                badge_number="KOL-001",
                department="Criminal Investigation",
            )
            officer_priya = Officer(
                username="officer_priya",
                full_name="Sub-Inspector Priya Menon",
                hashed_password=get_password_hash("Priya@002"),
                role="officer",
                badge_number="KOL-002",
                department="Criminal Investigation",
            )
            officer_arjun = Officer(
                username="officer_arjun",
                full_name="Constable Arjun Das",
                hashed_password=get_password_hash("Arjun@003"),
                role="viewer",
                badge_number="KOL-003",
                department="Field Operations",
            )
            db.add_all([officer_rakesh, officer_priya, officer_arjun])
            db.commit()

            # Seed sample persons for demo (no embeddings — they get added when photos are uploaded)
            _seed_sample_data(db)
    finally:
        db.close()


def _seed_sample_data(db):
    """Insert sample persons and records for demonstration."""
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

    for s in samples:
        crimes = s.pop("crimes")
        # No dummy embedding — embeddings are generated only from actual photos
        person = Person(**s)
        db.add(person)
        db.flush()

        for c in crimes:
            c["person_id"] = person.id
            db.add(CriminalRecord(**c))

    db.commit()
