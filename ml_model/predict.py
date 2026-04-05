import os
import numpy as np
import tensorflow as tf
from PIL import Image

# =========================
# Load model (SAFE PATH FIX)
# =========================
BASE_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(BASE_DIR, "flood_saved_model")

model = tf.saved_model.load(MODEL_PATH)
infer = model.signatures["serving_default"]

# =========================
# Image preprocessing
# =========================
IMG_SIZE = 224

def preprocess_image(image_path):
    img = Image.open(image_path).convert("RGB")
    img = img.resize((IMG_SIZE, IMG_SIZE))

    img_array = np.array(img) / 255.0
    img_array = np.expand_dims(img_array, axis=0).astype(np.float32)

    return img_array


# =========================
# Prediction function
# =========================
def predict_flood(image_path):
    img = preprocess_image(image_path)

    # 🔥 IMPORTANT: correct input key (MOST MODELS USE 'input_1')
    result = infer(keras_tensor=tf.constant(img))

    print("Full Output:", result)

    prediction = list(result.values())[0].numpy()[0][0]

    print("Raw Prediction:", prediction)

    # 🔁 Adjust if reversed (we'll confirm after testing)
    if prediction >= 0.5:
        return "No Flood"
    else:
        return "Flood"


# =========================
# Run test
# =========================
if __name__ == "__main__":
    image_path = os.path.join(BASE_DIR, "non-flood.png")  # keep test.jpg in ml_model folder
    result = predict_flood(image_path)
    print("Final Prediction:", result)