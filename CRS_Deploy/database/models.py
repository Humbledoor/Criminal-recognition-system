"""
SQLAlchemy ORM models for the Criminal Recognition System.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, ForeignKey, Enum
)
from sqlalchemy.orm import relationship, DeclarativeBase
import enum


class Base(DeclarativeBase):
    pass


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


# ── Officers (Users) ──────────────────────────────────────────────────
class Officer(Base):
    __tablename__ = "officers"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    full_name = Column(String(200), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default=OfficerRole.OFFICER.value)
    badge_number = Column(String(50))
    department = Column(String(200))
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    audit_logs = relationship("AuditLog", back_populates="officer")


# ── Persons ───────────────────────────────────────────────────────────
class Person(Base):
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(200), nullable=False)
    date_of_birth = Column(String(20))
    gender = Column(String(20))
    nationality = Column(String(100))
    address = Column(Text)
    government_id_number = Column(String(100))
    face_embedding_encrypted = Column(Text)          # AES-256 encrypted
    image_path = Column(String(500))
    record_status = Column(String(30), default=RecordStatus.CLEAN.value)
    risk_level = Column(String(10), default=RiskLevel.LOW.value)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    criminal_records = relationship("CriminalRecord", back_populates="person", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="person")


# ── Criminal Records ─────────────────────────────────────────────────
class CriminalRecord(Base):
    __tablename__ = "criminal_records"

    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    crime_type = Column(String(200), nullable=False)
    crime_description = Column(Text)
    case_number = Column(String(100))
    date_of_offense = Column(String(20))
    arrest_date = Column(String(20))
    conviction_status = Column(String(50))
    sentence_details = Column(Text)
    law_enforcement_agency = Column(String(200))
    court_name = Column(String(200))
    officer_notes = Column(Text)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    person = relationship("Person", back_populates="criminal_records")


# ── Audit Log ─────────────────────────────────────────────────────────
class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    officer_id = Column(Integer, ForeignKey("officers.id"), nullable=False)
    action_type = Column(String(20), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=True)
    details = Column(Text)
    ip_address = Column(String(50))

    officer = relationship("Officer", back_populates="audit_logs")
    person = relationship("Person", back_populates="audit_logs")
