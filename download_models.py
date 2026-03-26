import os
import urllib.request
import ssl

# Define model URL and destination
MODEL_URL = "https://github.com/opencv/opencv_zoo/raw/master/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
MODELS_DIR = os.path.join("face_pipeline", "models")
MODEL_PATH = os.path.join(MODELS_DIR, "face_recognition_sface.onnx")

def download_model():
    print("Checking if SFace model exists...")
    if os.path.exists(MODEL_PATH) and os.path.getsize(MODEL_PATH) > 10 * 1024 * 1024:
        print("Model already exists. Skipping download.")
        return

    print(f"Downloading SFace model from {MODEL_URL}...")
    os.makedirs(MODELS_DIR, exist_ok=True)
    
    # Bypass SSL verification if needed
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(MODEL_URL, context=context) as response, open(MODEL_PATH, 'wb') as out_file:
            data = response.read()
            out_file.write(data)
        print(f"Successfully downloaded model to {MODEL_PATH}")
    except Exception as e:
        print(f"Failed to download model: {e}")

if __name__ == "__main__":
    download_model()
