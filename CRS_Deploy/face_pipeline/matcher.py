"""
Face matching engine — compares query embedding against stored embeddings.
Uses cosine similarity with proper thresholds for FaceNet embeddings.
"""
import numpy as np
from sqlalchemy.orm import Session
from database.models import Person
from database.encryption import decrypt_embedding


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a_arr = np.array(a)
    b_arr = np.array(b)
    dot = np.dot(a_arr, b_arr)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def euclidean_distance(a: list[float], b: list[float]) -> float:
    """Compute Euclidean distance between two vectors."""
    return float(np.linalg.norm(np.array(a) - np.array(b)))


def search_matches(
    query_embedding: list[float],
    db: Session,
    threshold: float = 0.4,
    max_results: int = 10
) -> list[dict]:
    """
    Search the database for matching faces.
    Returns ranked list of matches above threshold.

    Threshold guide for OpenCV SFace embeddings (cosine similarity):
      - > 0.50 = Strong match (very likely same person)
      - ~ 0.363 = Standard match threshold
      - < 0.30 = Not a match
    """
    persons = db.query(Person).filter(Person.face_embedding_encrypted.isnot(None)).all()

    results = []
    for person in persons:
        try:
            stored_embedding = decrypt_embedding(person.face_embedding_encrypted)
        except Exception:
            continue

        # Ensure embeddings are the same dimension
        if len(stored_embedding) != len(query_embedding):
            continue

        cos_sim = cosine_similarity(query_embedding, stored_embedding)
        euc_dist = euclidean_distance(query_embedding, stored_embedding)

        # For OpenCV SFace normalized embeddings:
        # cosine sim >= 0.363 is considered a match
        # Convert similarity to a 0-100 score:
        # - < 0.20 => 0% (definitely not)
        # - 0.363 => 60% (match threshold)
        # - 1.0 => 100% (identical)
        if cos_sim < 0.20:
            confidence = 0.0
        elif cos_sim < 0.363:
            confidence = ((cos_sim - 0.20) / 0.163) * 59.9
        else:
            confidence = 60.0 + ((cos_sim - 0.363) / 0.637) * 40.0
        
        confidence = max(0.0, min(100.0, confidence))

        if cos_sim >= threshold:
            results.append({
                "person_id": person.id,
                "full_name": person.full_name,
                "confidence": round(confidence, 2),
                "cosine_similarity": round(cos_sim, 4),
                "euclidean_distance": round(euc_dist, 4),
                "record_status": person.record_status,
                "risk_level": person.risk_level,
                "date_of_birth": person.date_of_birth,
                "gender": person.gender,
                "nationality": person.nationality,
                "image_path": person.image_path,
            })

    # Sort by confidence descending
    results.sort(key=lambda x: x["confidence"], reverse=True)
    return results[:max_results]


def compute_bias_metrics(results: list[dict]) -> dict:
    """
    Compute bias monitoring metrics for search results.
    """
    if not results:
        return {"total_matches": 0}

    genders = {}
    nationalities = {}
    risk_levels = {}

    for r in results:
        g = r.get("gender", "Unknown") or "Unknown"
        genders[g] = genders.get(g, 0) + 1

        n = r.get("nationality", "Unknown") or "Unknown"
        nationalities[n] = nationalities.get(n, 0) + 1

        rl = r.get("risk_level", "Unknown") or "Unknown"
        risk_levels[rl] = risk_levels.get(rl, 0) + 1

    return {
        "total_matches": len(results),
        "avg_confidence": round(sum(r["confidence"] for r in results) / len(results), 2),
        "gender_distribution": genders,
        "nationality_distribution": nationalities,
        "risk_level_distribution": risk_levels,
    }
