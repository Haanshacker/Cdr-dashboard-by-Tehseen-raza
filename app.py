import streamlit as st
import pandas as pd
import base64

st.set_page_config(page_title="📱 CDR Dashboard by Tehseen", layout="wide")

st.markdown("<h1 style='text-align: center; color: #4CAF50;'>📊 CDR Dashboard</h1>", unsafe_allow_html=True)
st.markdown("Upload your CDR file below to begin analysis:")

uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.lower().str.strip()

    df.rename(columns={
        "calltype": "direction",
        "aparty": "caller",
        "bparty": "callee",
        "datetime": "start_time",
        "duration": "duration_sec",
        "imei": "imei",
        "sitelocation": "site"
    }, inplace=True)

    df["direction"] = df["direction"].str.lower().replace({
        "incoming sms": "sms_in",
        "incoming": "call_in",
        "outgoing": "call_out"
    })

    # MCC/MNC decoding (example logic)
    def decode_mcc_mnc(imei):
        if pd.isna(imei): return "Unknown"
        prefix = str(imei)[:5]
        mapping = {
            "41001": "Jazz",
            "41003": "Telenor",
            "41004": "Zong",
            "41006": "Ufone"
        }
        return mapping.get(prefix, "Other")

    df["operator"] = df["imei"].apply(decode_mcc_mnc)

    # Filters
    st.sidebar.header("📌 Filters")
    direction_filter = st.sidebar.multiselect("Call Direction", options=df["direction"].unique(), default=df["direction"].unique())
    operator_filter = st.sidebar.multiselect("Operator", options=df["operator"].unique(), default=df["operator"].unique())

    filtered_df = df[df["direction"].isin(direction_filter) & df["operator"].isin(operator_filter)]

    # Summary
    st.subheader("📈 Summary Stats")
    st.metric("Total Records", len(filtered_df))
    st.metric("Total Duration (sec)", int(filtered_df["duration_sec"].sum()))

    # Charts
    st.subheader("📊 Direction Breakdown")
    st.bar_chart(filtered_df["direction"].value_counts())

    st.subheader("📊 Operator Breakdown")
    st.bar_chart(filtered_df["operator"].value_counts())

    # Download filtered data
    def get_table_download_link(df):
        csv = df.to_csv(index=False)
        b64 = base64.b64encode(csv.encode()).decode()
        href = f'<a href="data:file/csv;base64,{b64}" download="filtered_cdr.csv">📥 Download Filtered Data</a>'
        return href

    st.markdown(get_table_download_link(filtered_df), unsafe_allow_html=True)
