"""
Face embedding extraction using OpenCV SFace (FaceRecognizerSF).
This provides highly accurate, pure Python/CV-based 128-dimensional face recognition.
Requires NO massive AI libraries like TensorFlow or DeepFace.
"""
import cv2
import numpy as np
from PIL import Image
import os

# Model config
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
DETECTOR_MODEL = os.path.join(MODEL_DIR, "face_detection_yunet.onnx")
RECOGNIZER_MODEL = os.path.join(MODEL_DIR, "face_recognition_sface.onnx")

# Lazy loading of models to prevent startup delays
_detector = None
_recognizer = None

def _get_models():
    """Initialize OpenCV Face models matching the ONNX files."""
    global _detector, _recognizer
    if _detector is None or _recognizer is None:
        if not os.path.exists(DETECTOR_MODEL) or not os.path.exists(RECOGNIZER_MODEL):
            print("[EMBEDDER] WARNING: OpenCV Models not found in", MODEL_DIR)
            return None, None
            
        # Initialize YuNet for face detection
        # Args: model, config, input_size, score_threshold, nms_threshold, top_k
        _detector = cv2.FaceDetectorYN.create(DETECTOR_MODEL, "", (320, 320), 0.5, 0.3, 5000)
        
        # Initialize SFace for recognition
        _recognizer = cv2.FaceRecognizerSF.create(RECOGNIZER_MODEL, "")
        print("[EMBEDDER] OpenCV SFace models loaded successfully!")
        
    return _detector, _recognizer


def extract_embedding(img: Image.Image) -> list[float] | None:
    """
    Extract a face embedding from a PIL Image using OpenCV SFace.
    Returns a normalized 128D embedding vector, or None if no face detected.
    """
    detector, recognizer = _get_models()
    if not detector or not recognizer:
        print("[EMBEDDER] Models missing, using pixel fallback")
        return _extract_pixel_embedding(img)
        
    # Convert PIL Image to OpenCV format (BGR)
    img_rgb = img.convert("RGB")
    img_cv2 = cv2.cvtColor(np.array(img_rgb), cv2.COLOR_RGB2BGR)
    
    height, width, _ = img_cv2.shape
    try:
        # Set dynamic input size
        detector.setInputSize((width, height))
        _, faces = detector.detect(img_cv2)
        
        if faces is None or len(faces) == 0:
            return None
            
        # Get the largest face
        faces = sorted(faces, key=lambda x: x[2]*x[3], reverse=True)
        main_face = faces[0]
        
        # Align and extract feature (128D array)
        aligned_face = recognizer.alignCrop(img_cv2, main_face)
        feature = recognizer.feature(aligned_face)
        
        # Normalize and convert to list
        embedding = feature[0]
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
            
        return embedding.tolist()
    except Exception as e:
        print(f"[EMBEDDER] OpenCV SFace Extraction Error: {e}")
        return None


def extract_multi_embedding(images: list[Image.Image]) -> list[float] | None:
    """
    Generate an averaged 128D embedding from multiple photos.
    """
    embeddings = []
    for i, img in enumerate(images):
        emb = extract_embedding(img)
        if emb is not None:
            embeddings.append(emb)
            
    if not embeddings:
        return None

    if len(embeddings) == 1:
        return embeddings[0]

    # Average all embeddings and normalize
    avg = np.mean(embeddings, axis=0)
    norm = np.linalg.norm(avg)
    if norm > 0:
        avg = avg / norm
    
    print(f"[EMBEDDER] Combined {len(embeddings)} photos using OpenCV SFace")
    return avg.tolist()


def _extract_pixel_embedding(img: Image.Image) -> list[float]:
    """
    Fallback 128-dim embedding (Not true recognition).
    """
    img_resized = img.resize((64, 64), Image.LANCZOS)
    gray = np.array(img_resized.convert("L"), dtype=np.float64) / 255.0
    
    features = []
    # Simple block means to just generate a 128D vector
    for i in range(0, 64, 8):
        for j in range(0, 64, 4):
            features.append(float(gray[i:i+8, j:j+4].mean()))
            
    features = features[:128]
    while len(features) < 128:
        features.append(0.0)

    embedding = np.array(features, dtype=np.float64)
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm

    return embedding.tolist()
