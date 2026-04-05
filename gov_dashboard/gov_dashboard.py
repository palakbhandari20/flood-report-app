import streamlit as st
import requests
import folium
import os
from streamlit_folium import st_folium

# ✅ Reads from environment variable — set this in Streamlit Cloud secrets
API = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

st.set_page_config(layout="wide")
st.title("🏛 Government Flood Monitoring Dashboard")

menu = st.sidebar.radio("Menu", ["Reports", "Rainfall Zones", "Alerts"])

# ---------------- REPORTS ----------------
if menu == "Reports":
    st.header("📊 User Reports")
    st.sidebar.subheader("📂 Filter Reports")

    filter_option = st.sidebar.selectbox("Show Reports", ["Latest", "Last 5", "Last 10", "All"])

    try:
        res = requests.get(f"{API}/reports", timeout=10)
        reports = res.json()
    except Exception:
        st.error("❌ Could not connect to backend. Is the API running?")
        reports = []

    if filter_option == "Latest":
        reports = reports[-1:] if reports else []
    elif filter_option == "Last 5":
        reports = reports[-5:]
    elif filter_option == "Last 10":
        reports = reports[-10:]

    if not reports:
        st.info("No reports yet.")

    for i, r in enumerate(reports):
        col1, col2 = st.columns([2, 1])

        with col1:
            st.write("📍 Location:", r["latitude"], r["longitude"])
            st.write("💬 Message:", r["message"])
            st.write("👤 Reported by:", r["user"])
            severity = r["severity"]
            if severity == "Flood":
                st.error(f"🚨 ML Result: {severity}")
            else:
                st.success(f"✅ ML Result: {severity}")

            if r.get("image_url"):
                st.image(r["image_url"], width=300)

        with col2:
            m = folium.Map(location=[r["latitude"], r["longitude"]], zoom_start=12)
            color = "red" if r["severity"] == "Flood" else "green"
            folium.Marker(
                [r["latitude"], r["longitude"]],
                icon=folium.Icon(color=color)
            ).add_to(m)
            st_folium(m, width=300, height=300, key=f"gov_map_{i}")

        st.divider()


# ---------------- ZONES ----------------
elif menu == "Rainfall Zones":
    st.header("🌧 Rainfall Zones Map")

    try:
        res = requests.get(f"{API}/zones", timeout=10)
        zones = res.json()
    except Exception:
        st.error("❌ Could not connect to backend.")
        zones = []

    m = folium.Map(location=[20, 78], zoom_start=5)

    for z in zones:
        color = z["zone"].lower()
        folium.Circle(
            location=[z["lat"], z["lon"]],
            radius=5000,
            color=color,
            fill=True,
            fill_opacity=0.5,
            popup=f"{color.upper()} ZONE"
        ).add_to(m)

    st_folium(m, width=1000, height=600, key="zones_map")


# ---------------- ALERTS ----------------
elif menu == "Alerts":
    st.header("🚨 Send Alert to User")

    zone = st.selectbox("Select Zone", ["RED", "ORANGE", "GREEN"])
    message = st.text_area("Message")
    user = st.text_input("Enter Username to send alert")

    if st.button("Send Alert"):
        try:
            res = requests.post(f"{API}/send-alert", json={
                "user": user,
                "zone": zone,
                "message": message
            })
            if res.status_code == 200:
                st.success("✅ Alert Sent")
            else:
                st.error("❌ Failed")
        except Exception:
            st.error("❌ Could not connect to backend.")

    st.markdown("---")
    st.subheader("📩 All Previous Alerts")

    try:
        res = requests.get(f"{API}/alerts", timeout=10)
        alerts = res.json()
        if alerts:
            for a in alerts:
                if a["zone"] == "RED":
                    st.error(f"🚨 [{a['user']}] {a['message']}")
                elif a["zone"] == "ORANGE":
                    st.warning(f"⚠️ [{a['user']}] {a['message']}")
                else:
                    st.success(f"✅ [{a['user']}] {a['message']}")
        else:
            st.info("No alerts sent yet.")
    except Exception:
        st.error("❌ Could not fetch alerts.")