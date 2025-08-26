import streamlit as st
import pandas as pd

# Page config
st.set_page_config(page_title="CDR Analysis by Tehseen Raza", layout="wide")

# Title
st.title("📊 CDR Analysis Dashboard by Tehseen Raza")
st.markdown("Upload your CDR file to view detailed call and SMS analysis directly inside the dashboard.")

# File upload
uploaded_file = st.file_uploader("Upload CDR CSV", type=["csv"])
if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.lower().str.strip()

    # Rename columns
    df.rename(columns={
        "calltype": "direction",
        "aparty": "caller",
        "bparty": "callee",
        "datetime": "start_time",
        "duration": "duration_sec",
        "imei": "imei",
        "sitelocation": "site"
    }, inplace=True)
# Step 1: Rename columns
df.rename(columns={
    "calltype": "direction",
    "aparty": "caller",
    "bparty": "callee",
    "datetime": "start_time",
    "duration": "duration_sec",
    "imei": "imei",
    "sitelocation": "site"
}, inplace=True)

# Step 2: Now you can safely convert to datetime
df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce")
    # Clean direction
    df["direction"] = df["direction"].str.lower().replace({
        "incoming sms": "sms_in",
        "incoming": "call_in",
        "outgoing": "call_out"
    })

    # Convert time
    df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce")

    # Status
    df["status"] = df["duration_sec"].apply(lambda x: "ANSWERED" if x > 0 else "NO_ANSWER")

    # Extract coordinates
    def extract_coords(site_str):
        try:
            parts = site_str.split("|")
            lat = float(parts[-2])
            lon = float(parts[-1])
            return lat, lon
        except:
            return None, None

    df["latitude"], df["longitude"] = zip(*df["site"].map(extract_coords))

    # Sidebar filters
    with st.sidebar:
        st.header("🔍 Filters")
        direction_filter = st.multiselect("Call Type", df["direction"].unique(), default=df["direction"].unique())
        date_range = st.date_input("Date Range", [df["start_time"].min().date(), df["start_time"].max().date()])
        df = df[df["direction"].isin(direction_filter)]
        df = df[(df["start_time"].dt.date >= date_range[0]) & (df["start_time"].dt.date <= date_range[1])]

    # KPIs
    col1, col2, col3 = st.columns(3)
    col1.metric("📞 Total Calls", df[df["direction"].str.contains("call")].shape[0])
    col2.metric("✉️ Total SMS", df[df["direction"].str.contains("sms")].shape[0])
    col3.metric("⏱️ Total Duration (sec)", int(df["duration_sec"].sum()))

    # Charts
    st.subheader("📈 Call Distribution")
    st.bar_chart(df["direction"].value_counts())

    st.subheader("📊 Duration by Call Type")
    st.area_chart(df.groupby("direction")["duration_sec"].sum())

    st.subheader("📅 Timeline of Activity")
    timeline = df.set_index("start_time").resample("H")["duration_sec"].sum()
    st.line_chart(timeline)
if "Datetime" not in df.columns:
    st.error("❌ 'Datetime' column not found in uploaded file.")
    st.stop()
    # Map
    st.subheader("🗺️ Cell Site Locations")
    st.map(df[["latitude", "longitude"]].dropna())

    # Data table
    st.subheader("📋 Filtered CDR Records")
    st.dataframe(df)

    # Download
    st.download_button("⬇️ Download Filtered Data", df.to_csv(index=False), "filtered_cdr.csv", "text/csv")

    # Footer
    st.markdown("---")
    st.markdown("© 2025 | Dashboard crafted by **Tehseen Raza**")
