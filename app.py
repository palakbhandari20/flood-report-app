# app.py
# Streamlit Flood Report UI with automatic browser geolocation (streamlit-javascript)
# Save as app.py and run: streamlit run app.py

import io
import json
import os
from datetime import datetime

import requests
import exifread
import folium
from PIL import Image
import streamlit as st
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderUnavailable, GeocoderTimedOut
from streamlit_javascript import st_javascript

# -------------------- Config --------------------
GOVERNMENT_ENDPOINT = "https://example.com/api/report"
USERS_FILE = "users.json"
UTTARAKHAND_GEOJSON_URL = (
    "https://raw.githubusercontent.com/geohacker/india/master/state/uttarakhand/uttarakhand_districts.geojson"
)

# -------------------- Streamlit page config --------------------
st.set_page_config(page_title="Flood Report UI", layout="wide")
st.title("Flood Report & Alert — Streamlit Demo")

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
            lat_ref = gps_lat_ref.values if hasattr(gps_lat_ref, "values") else str(gps_lat_ref)
            lon_ref = gps_lon_ref.values if hasattr(gps_lon_ref, "values") else str(gps_lon_ref)
            if isinstance(lat_ref, (list, tuple)):
                lat_ref = lat_ref[0]
            if isinstance(lon_ref, (list, tuple)):
                lon_ref = lon_ref[0]
            lat_dec = dms_to_decimal(lat, str(lat_ref))
            lon_dec = dms_to_decimal(lon, str(lon_ref))
            if lat_dec is not None and lon_dec is not None:
                return lat_dec, lon_dec
    except Exception:
        pass
    return None

def reverse_geocode(lat, lon, user_agent="flood_report_app"):
    try:
        geolocator = Nominatim(user_agent=user_agent, timeout=10)
        location = geolocator.reverse((lat, lon), language="en")
        return location.address if location else None
    except (GeocoderTimedOut, GeocoderUnavailable):
        return None
    except Exception:
        return None

def fetch_geojson(url):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None

# -------------------- Authentication / Registration --------------------
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
            # Clear relevant session state keys
            keys_to_clear = ["logged_in", "user", "login_user", "login_pwd", "reg_user", "reg_pwd", "browser_coords", "browser_error"]
            for k in keys_to_clear:
                if k in st.session_state:
                    try:
                        del st.session_state[k]
                    except Exception:
                        st.session_state[k] = None

            # Try to rerun; if not available, reload the page via JS
            try:
                st.experimental_rerun()
            except Exception:
                st.session_state.clear()
                st.markdown("<script>window.location.href = window.location.href;</script>", unsafe_allow_html=True)
                st.stop()

if not st.session_state.logged_in:
    st.info("Please register or login from the sidebar to continue.")
    st.stop()

# -------------------- Main UI --------------------
st.subheader("Report an incident")
col1, col2 = st.columns([1, 1])

with col1:
    camera_image = st.camera_input("📸 Take a live photo (use your webcam)")
    uploaded_file = st.file_uploader("Or upload image (photo with geotag preferred)", type=["png", "jpg", "jpeg", "heic"])
    uploaded_other = st.file_uploader("Upload additional file (pdf/image)", type=["pdf", "png", "jpg", "jpeg"], key="other")
    st.write("---")
    st.markdown("*Compose message to send to government / authority*")
    message = st.text_area("Message", height=150, placeholder="Describe the incident, location, severity, contact info...")
    severity = st.selectbox("Select alert severity (color)", ["Auto-detect", "Green (Low)", "Yellow (Medium)", "Red (High)"])
    send_to_gov = st.button("Send to Government")

    photo_file = None
    if camera_image is not None:
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

    # Browser location helper (explicit button)
    if "browser_coords" not in st.session_state:
        st.session_state.browser_coords = None
        st.session_state.browser_error = None

    st.markdown("**Automatic Browser Location**")
    st.write("Click the button below to allow the browser to share your location (you'll see a permission popup).")

    if st.button("Get browser location (allow in browser)"):
        js_code = """
        async () => {
          if (!navigator.geolocation) {
            return { error: "no_geolocation_support" };
          }
          try {
            const perm = await navigator.permissions.query({ name: 'geolocation' });
          } catch (e) { }
          return new Promise((resolve) => {
            navigator.geolocation.getCurrentPosition(
              (pos) => { resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }); },
              (err) => { resolve({ error: err.message || 'permission_denied_or_timeout' }); },
              { enableHighAccuracy: true, maximumAge: 0, timeout: 15000 }
            );
          });
        }
        """
        try:
            res = st_javascript(js_code, key=f"geo_js_{datetime.utcnow().timestamp()}")
            if isinstance(res, dict) and "lat" in res and "lon" in res:
                st.session_state.browser_coords = (float(res["lat"]), float(res["lon"]))
                st.session_state.browser_error = None
            else:
                st.session_state.browser_coords = None
                st.session_state.browser_error = res.get("error") if isinstance(res, dict) else "unknown_error"
        except Exception as e:
            st.session_state.browser_coords = None
            st.session_state.browser_error = str(e)

    if st.session_state.browser_coords:
        coords = st.session_state.browser_coords
        detected_place = reverse_geocode(*coords)
        st.success(f"Browser geolocation: {coords[0]:.6f}, {coords[1]:.6f}")
        if detected_place:
            st.caption(f"Detected address: {detected_place}")
    else:
        if st.session_state.get("browser_error"):
            st.info("Automatic location unavailable: " + str(st.session_state.browser_error))
        else:
            st.info("Automatic location not obtained. Click 'Get browser location' and allow location in browser when prompted.")

    # If no browser coords, try image EXIF
    if (not coords) and (photo_file is not None):
        try:
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
        except Exception:
            st.warning("Could not read image EXIF — maybe unsupported format.")

    # Manual geocoding fallback
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

    # Show map
    if coords:
        lat, lon = coords
        m = folium.Map(location=[lat, lon], zoom_start=12)
        gj = fetch_geojson(UTTARAKHAND_GEOJSON_URL)
        if gj:
            try:
                folium.GeoJson(gj, name="Uttarakhand districts").add_to(m)
            except Exception:
                pass

        color = "green"
        if severity == "Auto-detect":
            fn = getattr(photo_file, "name", "").lower() if photo_file is not None else ""
            caption = message.lower() if message else ""
            if any(k in fn for k in ["flood", "water", "flooding"]) or any(k in caption for k in ["flood", "water", "danger", "submerged"]):
                color = "red"
            else:
                color = "orange"
        elif severity.startswith("Green"):
            color = "green"
        elif severity.startswith("Yellow"):
            color = "orange"
        elif severity.startswith("Red"):
            color = "red"

        folium.CircleMarker(location=[lat, lon], radius=10, color=color, fill=True, fill_opacity=0.8, popup=detected_place or "Reported location").add_to(m)
        st_data = st_folium(m, width=700, height=500)
    else:
        st.info("No coordinates available yet. Allow browser location, upload/capture a photo with GPS, or enter a place name.")

# -------------------- Send action --------------------
if send_to_gov:
    payload = {
        "user": st.session_state.user,
        "message": message,
        "severity": severity,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "location": {
            "latitude": coords[0] if coords else None,
            "longitude": coords[1] if coords else None,
            "place": detected_place,
        },
    }

    files = {}
    if photo_file is not None:
        fname = getattr(photo_file, "name", None) or "camera_photo.jpg"
        files["image"] = (fname, photo_file.getvalue())
    if uploaded_other is not None:
        files["file"] = (uploaded_other.name, uploaded_other.getvalue())

    try:
        r = requests.post(GOVERNMENT_ENDPOINT, data={"payload": json.dumps(payload)}, files=files, timeout=15)
        if r.status_code in (200, 201, 202):
            st.success("Report sent to the endpoint successfully (placeholder).")
        else:
            st.warning(f"Request completed but returned status {r.status_code}. This is a demo endpoint.")
    except Exception as e:
        st.error(f"Failed to send report — error: {e}")

st.markdown("---")
st.caption("Demo app: replace placeholder endpoint before production. Browser geolocation requires HTTPS (or localhost for testing).")
