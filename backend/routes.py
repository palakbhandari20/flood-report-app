from fastapi import APIRouter, UploadFile, File, Form
from backend.database import SessionLocal
from backend.models import Report
from backend.rainfall_service import get_rainfall_zone
import sys
import os
import uuid

# Access ML model
sys.path.append("..")
from ml_model.predict import predict_flood

router = APIRouter()
alerts = []  # in-memory alerts storage

# -------------------------
# Supabase Storage Setup
# -------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "flood-images")
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

def upload_image_to_supabase(file_bytes: bytes, filename: str) -> str:
    """Upload image to Supabase Storage and return public URL."""
    try:
        import httpx
        unique_name = f"{uuid.uuid4()}_{filename}"
        upload_url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{unique_name}"
        headers = {
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "image/jpeg",
        }
        res = httpx.put(upload_url, content=file_bytes, headers=headers)
        if res.status_code in [200, 201]:
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{unique_name}"
            return public_url
    except Exception as e:
        print(f"Supabase upload error: {e}")
    return ""

def save_image_locally(file_bytes: bytes, filename: str) -> str:
    """Fallback: save image locally."""
    os.makedirs("data/uploads", exist_ok=True)
    file_location = f"data/uploads/{filename}"
    with open(file_location, "wb") as f:
        f.write(file_bytes)
    return file_location


# -----------------------------
# CREATE REPORT
# -----------------------------
@router.post("/report")
async def create_report(
    message: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    user: str = Form(...),
    image: UploadFile = File(...)
):
    db = SessionLocal()
    file_bytes = await image.read()

    if USE_SUPABASE:
        # Upload to Supabase Storage
        image_url = upload_image_to_supabase(file_bytes, image.filename)
        image_path = image_url
    else:
        # Save locally (for local dev)
        local_path = save_image_locally(file_bytes, image.filename)
        image_path = local_path
        # Save temp file for ML prediction
        temp_path = f"/tmp/{image.filename}"
        with open(temp_path, "wb") as f:
            f.write(file_bytes)
        local_path = temp_path

    # Save temp file for ML prediction
    temp_path = f"/tmp/{uuid.uuid4()}_{image.filename}"
    with open(temp_path, "wb") as f:
        f.write(file_bytes)

    # ML prediction
    prediction = predict_flood(temp_path)

    # Clean up temp file
    try:
        os.remove(temp_path)
    except Exception:
        pass

    report = Report(
        user=user,
        message=message,
        latitude=latitude,
        longitude=longitude,
        severity=prediction,
        image_path=image_path
    )

    db.add(report)
    db.commit()

    return {
        "status": "report stored",
        "prediction": prediction
    }


# -----------------------------
# GET REPORTS (FOR GOV DASHBOARD)
# -----------------------------
@router.get("/reports")
def get_reports():
    db = SessionLocal()
    reports = db.query(Report).all()

    BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

    result = []
    for r in reports:
        # If image_path is already a full URL (Supabase), use as-is
        if r.image_path and r.image_path.startswith("http"):
            image_url = r.image_path
        else:
            image_url = f"{BASE_URL}/{r.image_path}"

        result.append({
            "id": r.id,
            "user": r.user,
            "message": r.message,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "severity": r.severity,
            "image_url": image_url
        })

    return result


# -----------------------------
# RAINFALL ZONE (SINGLE)
# -----------------------------
@router.get("/rainfall-zone")
def rainfall_zone(latitude: float, longitude: float):
    result = get_rainfall_zone(latitude, longitude)
    return {
        "latitude": latitude,
        "longitude": longitude,
        "rainfall_mm": result["rainfall_mm"],
        "zone": result["zone"]
    }


# -----------------------------
# ALL ZONES (FOR GOV MAP)
# -----------------------------
@router.get("/zones")
def get_all_zones():
    db = SessionLocal()
    reports = db.query(Report).all()

    zones = []
    for r in reports:
        zone_data = get_rainfall_zone(r.latitude, r.longitude)
        zones.append({
            "lat": r.latitude,
            "lon": r.longitude,
            "zone": zone_data["zone"]
        })

    return zones


# -----------------------------
# ALERT SYSTEM
# -----------------------------
@router.post("/send-alert")
def send_alert(data: dict):
    alerts.append({
        "user": data.get("user"),
        "zone": data.get("zone"),
        "message": data.get("message")
    })
    return {"message": "Alert sent successfully"}

@router.get("/alerts/{username}")
def get_user_alerts(username: str):
    return [a for a in alerts if a["user"] == username]

@router.get("/alerts")
def get_alerts():
    return alerts