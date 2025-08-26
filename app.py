import streamlit as st
import pandas as pd
import numpy as np

# ---------- Page Config ----------
st.set_page_config(page_title="Telecom CDR Dashboard", layout="wide")

# ---------- Header ----------
st.title("📊 Telecom CDR Dashboard")
st.markdown("Analyze call and SMS records with location, duration, and device insights.")

# ---------- File Upload ----------
uploaded_file = st.file_uploader("Upload your CDR CSV file", type=["csv"])
if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.lower().str.strip()

    # ---------- Rename Columns ----------
    df.rename(columns={
        "calltype": "direction",
        "aparty": "caller",
        "bparty": "callee",
        "datetime": "start_time",
        "duration": "duration_sec",
        "imei": "imei",
        "sitelocation": "site"
    }, inplace=True)

    # ---------- Clean & Transform ----------
    df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce")
    df["direction"] = df["direction"].str.lower().replace({
        "incoming sms": "sms_in",
        "incoming": "call_in",
        "outgoing": "call_out"
    })
    df["status"] = df["duration_sec"].apply(lambda x: "ANSWERED" if x > 0 else "NO_ANSWER")

    # ---------- Extract Coordinates ----------
    def extract_coords(site_str):
        try:
            parts = site_str.split("|")
            lat = float(parts[-2])
            lon = float(parts[-1])
            return lat, lon
        except:
            return None, None

    df["latitude"], df["longitude"] = zip(*df["site"].map(extract_coords))

    # ---------- Sidebar Filters ----------
    with st.sidebar:
        st.header("🔍 Filters")
        direction_filter = st.multiselect("Call Type", df["direction"].unique(), default=df["direction"].unique())
        date_range = st.date_input("Date Range", [df["start_time"].min().date(), df["start_time"].max().date()])
        df = df[df["direction"].isin(direction_filter)]
        df = df[(df["start_time"].dt.date >= date_range[0]) & (df["start_time"].dt.date <= date_range[1])]

    # ---------- KPI Cards ----------
    col1, col2, col3 = st.columns(3)
    col1.metric("📞 Total Calls", df[df["direction"].str.contains("call")].shape[0])
    col2.metric("✉️ Total SMS", df[df["direction"].str.contains("sms")].shape[0])
    col3.metric("⏱️ Total Duration (sec)", int(df["duration_sec"].sum()))

    # ---------- Charts ----------
    st.subheader("📈 Call Distribution")
    st.bar_chart(df["direction"].value_counts())

    st.subheader("📊 Duration by Call Type")
    st.area_chart(df.groupby("direction")["duration_sec"].sum())

    st.subheader("📅 Timeline of Activity")
    timeline = df.set_index("start_time").resample("H")["duration_sec"].sum()
    st.line_chart(timeline)

    # ---------- Map ----------
    st.subheader("🗺️ Cell Site Locations")
    st.map(df[["latitude", "longitude"]].dropna())

    # ---------- Data Table & Download ----------
    st.subheader("📋 Filtered CDR Records")
    st.dataframe(df)

    st.download_button("⬇️ Download Filtered Data", df.to_csv(index=False), "filtered_cdr.csv", "text/csv")
