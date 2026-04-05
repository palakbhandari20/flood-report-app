import streamlit as st
import requests
import folium
from streamlit_folium import st_folium

API = "http://127.0.0.1:8000"

st.set_page_config(layout="wide")
st.title("🏛 Government Flood Monitoring Dashboard")

menu = st.sidebar.radio("Menu", ["Reports", "Rainfall Zones", "Alerts"])

# ---------------- REPORTS ----------------
if menu == "Reports":

    st.header("📊 User Reports")
    st.sidebar.subheader("📂 Filter Reports")

    filter_option = st.sidebar.selectbox(
        "Show Reports",
        ["Latest", "Last 5", "Last 10", "All"]
    )

    res = requests.get(f"{API}/reports")
    reports = res.json()
    if filter_option == "Latest":
        reports = reports[-1:] if reports else []

    elif filter_option == "Last 5":
        reports = reports[-5:]

    elif filter_option == "Last 10":
        reports = reports[-10:]

    elif filter_option == "All":
        pass

    for i,r in enumerate(reports):

        col1, col2 = st.columns([2,1])

        with col1:
            st.write("📍 Location:", r["latitude"], r["longitude"])
            st.write("💬 Message:", r["message"])
            st.write("🚨 ML Result:", r["severity"])

            # 🔥 DEBUG (optional)
            # st.write(r)

            st.image(r["image_url"], width=300)

        with col2:
            m = folium.Map(location=[r["latitude"], r["longitude"]], zoom_start=12)

            color = "green"
            if r["severity"] == "Flood":
                color = "red"

            folium.Marker(
                [r["latitude"], r["longitude"]],
                icon=folium.Icon(color=color)
            ).add_to(m)

            st_folium(m, width=300, height=300,key=f"gov_map_{i}")

        st.divider()


# ---------------- ZONES ----------------
elif menu == "Rainfall Zones":

    st.header("🌧 Rainfall Zones Map")

    res = requests.get(f"{API}/zones")
    zones = res.json()

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

    st.header("🚨 Send Alert")

    zone = st.selectbox("Select Zone", ["RED", "ORANGE", "GREEN"])
    message = st.text_area("Message")
    user = st.text_input("Enter Username to send alert")
    if st.button("Send Alert"):
        res = requests.post(f"{API}/send-alert", json={
            "user": user,
            "zone": zone,
            "message": message
        })

        if res.status_code == 200:
            st.success("✅ Alert Sent")
        else:
            st.error("❌ Failed")

    st.markdown("---")
    st.subheader("📩 Previous Alerts")

    res = requests.get(f"{API}/alerts")
    alerts = res.json()

    for a in alerts:
        st.write(a)