"""
Streamlit app: Flood report UI (with both live camera capture and file upload)
- Use webcam: st.camera_input("...") (preferred if present)
- Or upload an image (jpg/png/heic)
- Extract GPS EXIF if present
- Geocode addresses (Nominatim) if needed
- Show folium map and marker
- Send report (with chosen image/file) to a placeholder endpoint
"""

import streamlit as st
from PIL import Image
import exifread
import io
import json
import os
import requests
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderUnavailable, GeocoderTimedOut

# -------------------- Config --------------------
USERS_FILE = "users.json"
GOVERNMENT_ENDPOINT = "https://example.com/api/report"  # <-- Replace with real endpoint
UTTARAKHAND_GEOJSON_URL = (
    "https://raw.githubusercontent.com/geohacker/india/master/state/uttarakhand/uttarakhand_districts.geojson"
)

# -------------------- Helpers --------------------
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        try:
            return json.load(f)
        except Exception:
            return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

def register_user(username, password):
    users = load_users()
    if username in users:
        return False, "Username already exists"
    users[username] = {"password": password}
    save_users(users)
    return True, "Registered"

def verify_user(username, password):
    users = load_users()
    if username in users and users[username].get("password") == password:
        return True
    return False

def dms_to_decimal(dms, ref):
    try:
        degrees = float(dms[0])
        minutes = float(dms[1])
        seconds = float(dms[2])
        dec = degrees + minutes / 60.0 + seconds / 3600.0
        if ref in ["S", "W"]:
            dec = -dec
        return dec
    except Exception:
        return None

def extract_gps_from_exif(file_bytes):
    try:
        tags = exifread.process_file(io.BytesIO(file_bytes), details=False)
        gps_lat = tags.get("GPS GPSLatitude")
        gps_lat_ref = tags.get("GPS GPSLatitudeRef")
        gps_lon = tags.get("GPS GPSLongitude")
        gps_lon_ref = tags.get("GPS GPSLongitudeRef")
        if gps_lat and gps_lon and gps_lat_ref and gps_lon_ref:
            lat = [float(x.num) / float(x.den) for x in gps_lat.values]
            lon = [float(x.num) / float(x.den) for x in gps_lon.values]
            lat_ref = gps_lat_ref.values
            lon_ref = gps_lon_ref.values
            lat_dec = dms_to_decimal(lat, lat_ref)
            lon_dec = dms_to_decimal(lon, lon_ref)
            if lat_dec is not None and lon_dec is not None:
                return lat_dec, lon_dec
    except Exception:
        pass
    return None

def reverse_geocode(lat, lon, user_agent="flood_report_app"):
    geolocator = Nominatim(user_agent=user_agent, timeout=10)
    try:
        location = geolocator.reverse((lat, lon), language="en")
        return location.address if location else None
    except (GeocoderTimedOut, GeocoderUnavailable):
        return None

def fetch_geojson(url):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None

# -------------------- Streamlit UI --------------------
st.set_page_config(page_title="Flood Report UI", layout="wide")
st.title("Flood Report & Alert — Streamlit Demo")

# --- Authentication / Registration ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

with st.sidebar:
    st.header("Account")
    if not st.session_state.logged_in:
        tab = st.tabs(["Login", "Register"])
        with tab[0]:
            st.subheader("Login")
            user = st.text_input("Username", key="login_user")
            pwd = st.text_input("Password", type="password", key="login_pwd")
            if st.button("Login"):
                if verify_user(user, pwd):
                    st.session_state.logged_in = True
                    st.session_state.user = user
                    st.success(f"Logged in as {user}")
                else:
                    st.error("Invalid username or password")
        with tab[1]:
            st.subheader("Register")
            new_user = st.text_input("New username", key="reg_user")
            new_pwd = st.text_input("New password", type="password", key="reg_pwd")
            if st.button("Register"):
                ok, msg = register_user(new_user, new_pwd)
                if ok:
                    st.success("Registered — you can now login")
                else:
                    st.error(msg)
    else:
        st.markdown(f"*User:* {st.session_state.user}")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.experimental_rerun()

# If not logged in, show info and stop
if not st.session_state.logged_in:
    st.info("Please register or login from the sidebar to continue.")
    st.stop()

# --- Main app ---
st.subheader("Report an incident")
col1, col2 = st.columns([1, 1])

with col1:
    # Live camera capture (preferred if present)
    camera_image = st.camera_input("📸 Take a live photo (use your webcam)")

    # Traditional upload
    uploaded_file = st.file_uploader("Or upload image (photo with geotag preferred)", type=["png", "jpg", "jpeg", "heic"])

    # Additional file upload
    uploaded_other = st.file_uploader("Upload additional file (pdf/image)", type=["pdf", "png", "jpg", "jpeg"], key="other")

    st.write("---")
    st.markdown("*Compose message to send to government / authority*")
    message = st.text_area("Message", height=150, placeholder="Describe the incident, location, severity, contact info...")
    severity = st.selectbox("Select alert severity (color)", ["Auto-detect", "Green (Low)", "Yellow (Medium)", "Red (High)"])
    send_to_gov = st.button("Send to Government")

    # Decide which image to use: prefer camera capture if present, otherwise uploaded file
    photo_file = None
    if camera_image is not None:
        # preview camera capture
        try:
            st.image(Image.open(io.BytesIO(camera_image.getvalue())), caption="Captured photo (live)", use_column_width=True)
        except Exception:
            st.write("(Cannot preview captured photo)")
        photo_file = camera_image
    elif uploaded_file is not None:
        try:
            st.image(Image.open(io.BytesIO(uploaded_file.getvalue())), caption="Uploaded image", use_column_width=True)
        except Exception:
            st.write("(Can't preview this image)")
        photo_file = uploaded_file

with col2:
    st.markdown("*Location extraction & Map*")
    coords = None
    detected_place = None

    # Try extracting GPS from chosen photo (camera or uploaded)
    if photo_file is not None:
        file_bytes = photo_file.getvalue()
        gps = extract_gps_from_exif(file_bytes)
        if gps:
            coords = gps
            detected_place = reverse_geocode(*coords)
            st.success(f"GPS extracted: {coords[0]:.6f}, {coords[1]:.6f}")
            if detected_place:
                st.caption(f"Detected address: {detected_place}")
        else:
            st.warning("No GPS EXIF found in the image. Camera photos often have no EXIF; you can type a place name manually below.")

    # Manual place name fallback
    place_text = st.text_input("Or enter location name (e.g., Dehradun, Uttarakhand)")
    if not coords and place_text:
        try:
            geolocator = Nominatim(user_agent="flood_report_app")
            loc = geolocator.geocode(place_text, timeout=10)
            if loc:
                coords = (loc.latitude, loc.longitude)
                detected_place = loc.address
                st.success(f"Geocoded: {coords[0]:.6f}, {coords[1]:.6f}")
                st.caption(f"Detected address: {detected_place}")
            else:
                st.error("Could not geocode the provided place name")
        except Exception:
            st.error("Geocoding service unavailable — please try later")

    # Show map if coords present
    if coords:
        lat, lon = coords
        m = folium.Map(location=[lat, lon], zoom_start=10)

        # Attempt to fetch Uttarakhand geojson and overlay
        gj = fetch_geojson(UTTARAKHAND_GEOJSON_URL)
        if gj:
            try:
                folium.GeoJson(gj, name="Uttarakhand districts").add_to(m)
            except Exception:
                pass

        # Determine marker color based on severity or auto
        color = "green"
        if severity == "Auto-detect":
            fn = getattr(photo_file, "name", "").lower() if photo_file is not None else ""
            caption = message.lower() if message else ""
            if any(k in fn for k in ["flood", "water", "flooding"]) or any(k in caption for k in ["flood", "water", "danger", "submerged"]):
                color = "red"
            else:
                color = "yellow"
        elif severity.startswith("Green"):
            color = "green"
        elif severity.startswith("Yellow"):
            color = "orange"
        elif severity.startswith("Red"):
            color = "red"

        folium.CircleMarker(location=[lat, lon], radius=10, color=color, fill=True, fill_opacity=0.8, popup=detected_place or "Reported location").add_to(m)
        st_data = st_folium(m, width=700, height=500)
    else:
        st.info("No coordinates available yet. Upload / capture a photo with GPS or enter a place name.")

# --- Send action ---
if send_to_gov:
    payload = {
        "user": st.session_state.user,
        "message": message,
        "severity": severity,
        "location": {
            "latitude": coords[0] if coords else None,
            "longitude": coords[1] if coords else None,
            "place": detected_place,
        },
    }

    files = {}
    # Attach chosen image (camera or uploaded)
    if photo_file is not None:
        fname = getattr(photo_file, "name", None) or "camera_photo.jpg"
        files["image"] = (fname, photo_file.getvalue())
    if uploaded_other is not None:
        files["file"] = (uploaded_other.name, uploaded_other.getvalue())

    try:
        # NOTE: This POSTS to a placeholder endpoint. Replace with your backend API and add auth.
        r = requests.post(GOVERNMENT_ENDPOINT, data={"payload": json.dumps(payload)}, files=files, timeout=15)
        if r.status_code in (200, 201, 202):
            st.success("Report sent to the endpoint successfully (placeholder)")
        else:
            st.warning(f"Request completed but returned status {r.status_code}. This is a demo endpoint.")
    except Exception as e:
        st.error(f"Failed to send report — error: {e}")

# --- Footer ---
st.markdown("---")
st.caption("This is a demo app. Camera capture may not include GPS. For accurate location include coordinates or type place name. Replace placeholder endpoint before deploying.")
