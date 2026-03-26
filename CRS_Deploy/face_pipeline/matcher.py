"""
Face matching engine — compares query embedding against stored embeddings.
Adapted for Firebase Firestore.
"""
import numpy as np
from google.cloud import firestore
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
    db: firestore.Client,
    threshold: float = 0.4,
    max_results: int = 10
) -> list[dict]:
    """
    Search the database for matching faces.
    Returns ranked list of matches above threshold.
    """
    # In Firestore, we must retrieve all persons with an embedding
    # and compute similarity in memory. This is standard for small datasets.
    # For millions of records, a vector DB (Pinecone, Milvus) is required.
    
    persons_ref = db.collection("persons")
    # Firebase doesn't have "isnot(None)" easily without composite indexes
    # But we can just stream all and filter
    docs = persons_ref.stream()

    results = []
    
    for doc in docs:
        person = doc.to_dict()
        enc_emb = person.get("face_embedding_encrypted")
        
        if not enc_emb:
            continue
            
        try:
            stored_embedding = decrypt_embedding(enc_emb)
        except Exception:
            continue

        # Ensure embeddings are the same dimension
        if len(stored_embedding) != len(query_embedding):
            continue

        cos_sim = cosine_similarity(query_embedding, stored_embedding)
        euc_dist = euclidean_distance(query_embedding, stored_embedding)

        if cos_sim < 0.20:
            confidence = 0.0
        elif cos_sim < 0.363:
            confidence = ((cos_sim - 0.20) / 0.163) * 59.9
        else:
            confidence = 60.0 + ((cos_sim - 0.363) / 0.637) * 40.0
        
        confidence = max(0.0, min(100.0, confidence))

        if cos_sim >= threshold:
            # Fetch criminal records for this person
            person_id = person.get("id")
            crime_types = []
            total_cases = 0
            try:
                records_docs = db.collection("criminal_records").where("person_id", "==", person_id).stream()
                for rec_doc in records_docs:
                    rec = rec_doc.to_dict()
                    ct = rec.get("crime_type")
                    if ct and ct not in crime_types:
                        crime_types.append(ct)
                    total_cases += 1
            except Exception:
                pass

            results.append({
                "person_id": person_id,
                "full_name": person.get("full_name"),
                "confidence": round(confidence, 2),
                "cosine_similarity": round(cos_sim, 4),
                "euclidean_distance": round(euc_dist, 4),
                "record_status": person.get("record_status"),
                "risk_level": person.get("risk_level"),
                "date_of_birth": person.get("date_of_birth"),
                "gender": person.get("gender"),
                "nationality": person.get("nationality"),
                "image_path": person.get("image_path"),
                "crime_types": crime_types,
                "total_cases": total_cases,
                "last_seen_location": person.get("address") or "Unknown",
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
