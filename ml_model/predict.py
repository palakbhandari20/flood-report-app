import os
import numpy as np
from PIL import Image

IMG_SIZE = 224
model = None

def load_model():
    global model
    if model is not None:
        return model

    import tensorflow as tf
    from huggingface_hub import hf_hub_download

    base_dir = "/tmp/flood_model"
    os.makedirs(f"{base_dir}/variables", exist_ok=True)

    # Download model files from Hugging Face
    hf_hub_download(repo_id="palakbhandari20/flood-classification-model", filename="saved_model.pb", local_dir=base_dir)
    hf_hub_download(repo_id="palakbhandari20/flood-classification-model", filename="variables.index", local_dir=f"{base_dir}/variables")
    hf_hub_download(repo_id="palakbhandari20/flood-classification-model", filename="variables.data-00000-of-00001", local_dir=f"{base_dir}/variables")

    model = tf.saved_model.load(base_dir)
    return model

def preprocess_image(image_path):
    img = Image.open(image_path).convert("RGB")
    img = img.resize((IMG_SIZE, IMG_SIZE))
    img_array = np.array(img) / 255.0
    img_array = np.expand_dims(img_array, axis=0).astype(np.float32)
    return img_array

def predict_flood(image_path):
    try:
        import tensorflow as tf
        m = load_model()
        infer = m.signatures["serving_default"]
        img = preprocess_image(image_path)
        result = infer(keras_tensor=tf.constant(img))
        prediction = list(result.values())[0].numpy()[0][0]
        if prediction >= 0.5:
            return "No Flood"
        else:
            return "Flood"
    except Exception as e:
        print(f"ML prediction error: {e}")
        return "Flood"