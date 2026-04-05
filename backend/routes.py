from fastapi import APIRouter, UploadFile, File, Form
from backend.database import SessionLocal
from backend.models import Report
from backend.rainfall_service import get_rainfall_zone
import sys
import os

# access ML model
sys.path.append("..")
from ml_model.predict import predict_flood

router = APIRouter()

alerts = []   # in-memory alerts storage


# -----------------------------
# CREATE REPORT (USER → BACKEND)
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

    os.makedirs("data/uploads", exist_ok=True)
    file_location = f"data/uploads/{image.filename}"

    # save image
    with open(file_location, "wb") as f:
        f.write(await image.read())

    # ML prediction
    prediction = predict_flood(file_location)

    report = Report(
        user=user,
        message=message,
        latitude=latitude,
        longitude=longitude,
        severity=prediction,
        image_path=file_location
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

    result = []
    for r in reports:
        result.append({
            "id": r.id,
            "user": r.user,
            "message": r.message,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "severity": r.severity,
            "image_url": f"http://127.0.0.1:8000/{r.image_path}"
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
alerts = []

@router.post("/send-alert")
def send_alert(data: dict):
    alerts.append({
        "user": data.get("user"),   # 🔥 IMPORTANT
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