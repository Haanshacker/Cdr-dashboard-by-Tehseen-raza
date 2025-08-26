# app.py
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import datetime, timedelta, date

st.set_page_config(page_title="CDR Analysis Dashboard", layout="wide")

# -------------------------------
# Utilities
# -------------------------------
@st.cache_data(show_spinner=False)
def load_data(file):
    # Support CSV and Excel
    name = getattr(file, "name", "upload").lower()
    if name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(file)
    else:
        try:
            df = pd.read_csv(file)
        except UnicodeDecodeError:
            file.seek(0)
            df = pd.read_csv(file, encoding="latin1")
    return df

def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    # Normalize column names
    col_map = {c: c.strip().lower().replace(" ", "_") for c in df.columns}
    df = df.rename(columns=col_map)

    # Heuristic mapping to canonical names
    mapping_candidates = {
        "start_time": ["start_time", "call_start", "start", "timestamp", "start_datetime", "setup_time", "connect_time", "event_time"],
        "end_time": ["end_time", "call_end", "end", "release_time", "disconnect_time"],
        "duration_sec": ["duration_sec", "duration", "call_duration", "bill_sec", "billable_seconds", "talk_time", "conversation_time_sec"],
        "caller": ["caller", "calling", "calling_party", "a_number", "ani", "msisdn_a"],
        "callee": ["callee", "called", "called_party", "b_number", "dnis", "msisdn_b"],
        "direction": ["direction", "call_direction", "in_out", "inbound_outbound"],
        "status": ["status", "cause", "release_cause", "disposition", "result", "sip_response", "q850_cause"],
        "operator": ["operator", "carrier", "vendor", "trunk", "gateway", "route"],
        "country": ["country", "dest_country", "destination_country"],
        "mcc": ["mcc"],
        "mnc": ["mnc"],
        "cell_id": ["cell_id", "cellid", "cell", "lac_cell"],
        "imsi": ["imsi"],
        "imei": ["imei"],
        "setup_time_ms": ["setup_time_ms", "post_dial_delay_ms", "pdd_ms", "ring_time_ms"],
        "cost": ["cost", "charge", "amount", "revenue"]
    }

    canon = {}
    for k, candidates in mapping_candidates.items():
        for cand in candidates:
            if cand in df.columns:
                canon[k] = cand
                break

    out = df.copy()

    # Parse datetimes
    if "start_time" in canon:
        out["start_time"] = pd.to_datetime(out[canon["start_time"]], errors="coerce")
    else:
        # Try to infer any datetime column
        found = False
        for c in out.columns:
            if any(s in c for s in ["time", "date"]):
                try_col = pd.to_datetime(out[c], errors="coerce")
                if try_col.notna().mean() > 0.6:
                    out["start_time"] = try_col
                    canon["start_time"] = c
                    found = True
                    break
        if not found:
            out["start_time"] = pd.NaT

    if "end_time" in canon:
        out["end_time"] = pd.to_datetime(out[canon["end_time"]], errors="coerce")
    else:
        out["end_time"] = pd.NaT

    # Duration in seconds
    if "duration_sec" in canon:
        out["duration_sec"] = pd.to_numeric(out[canon["duration_sec"]], errors="coerce")
    else:
        if out["end_time"].notna().any() and out["start_time"].notna().any():
            out["duration_sec"] = (out["end_time"] - out["start_time"]).dt.total_seconds()
        else:
            out["duration_sec"] = np.nan

    # Core identifiers
    for k in ["caller", "callee", "direction", "status", "operator", "country", "mcc", "mnc", "cell_id", "imsi", "imei"]:
        if k in canon:
            out[k] = out[canon[k]].astype(str)
        else:
            out[k] = np.nan

    # Optional metrics
    out["setup_time_ms"] = pd.to_numeric(out[canon["setup_time_ms"]], errors="coerce") if "setup_time_ms" in canon else np.nan
    out["cost"] = pd.to_numeric(out[canon["cost"]], errors="coerce") if "cost" in canon else np.nan

    # Derived fields
    status_upper = out["status"].astype(str).str.upper()
    out["answered"] = status_upper.str.contains("ANSWER|OK|200", na=False)
    out["failed"] = status_upper.str.contains("FAIL|BUSY|NO_ANSWER|486|480|503|CONGEST", na=False)
    out["date"] = pd.to_datetime(out["start_time"]).dt.date
    out["hour"] = pd.to_datetime(out["start_time"]).dt.hour
    out["weekday"] = pd.to_datetime(out["start_time"]).dt.day_name()

    # Clean direction
    out["direction"] = (
        out["direction"]
        .str.lower()
        .replace({"in": "inbound", "out": "outbound", "incoming": "inbound", "outgoing": "outbound"})
    )

    # Keep valid rows
    out = out[out["start_time"].notna()].copy()
    return out

def filter_data(df):
    df = df.copy()
    with st.sidebar:
        st.header("Filters")

        # Date range
        if df["start_time"].notna().any():
            min_d = df["start_time"].min().date()
            max_d = df["start_time"].max().date()
        else:
            today = date.today()
            min_d, max_d = today - timedelta(days=30), today
        date_rng = st.date_input("Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
        if isinstance(date_rng, tuple) and len(date_rng) == 2:
            start_d, end_d = date_rng
            df = df[(df["start_time"].dt.date >= start_d) & (df["start_time"].dt.date <= end_d)]

        # Direction
        dir_opts = sorted([d for d in df["direction"].dropna().unique() if d])
        sel_dir = st.multiselect("Direction", dir_opts, default=dir_opts)
        if sel_dir:
            df = df[df["direction"].isin(sel_dir)]

        # Status
        status_opts = sorted([s for s in df["status"].dropna().unique() if s])
        sel_status = st.multiselect("Status", status_opts, default=status_opts[:20] if len(status_opts) > 20 else status_opts)
        if sel_status:
            df = df[df["status"].isin(sel_status)]

        # Operator
        op_opts = sorted([o for o in df["operator"].dropna().unique() if o and o != "nan"])
        sel_ops = st.multiselect("Operator/Carrier", op_opts)
        if sel_ops:
            df = df[df["operator"].isin(sel_ops)]

        # Country
        ctry_opts = sorted([c for c in df["country"].dropna().unique() if c and c != "nan"])
        sel_ctry = st.multiselect("Country", ctry_opts)
        if sel_ctry:
            df = df[df["country"].isin(sel_ctry)]

        # Duration range
        if df["duration_sec"].notna().any():
            d_min, d_max = float(df["duration_sec"].min()), float(df["duration_sec"].max())
            dur = st.slider("Duration filter (seconds)", min_value=0.0, max_value=max(1.0, d_max), value=(0.0, max(1.0, d_max)))
            df = df[(df["duration_sec"].fillna(0) >= dur[0]) & (df["duration_sec"].fillna(0) <= dur[1])]

    return df

def kpi_cards(df):
    total_calls = len(df)
    answered_calls = int(df["answered"].sum())
    total_minutes = df["duration_sec"].fillna(0).sum() / 60.0
    asr = (answered_calls / total_calls) if total_calls else 0.0
    acd_min = df.loc[df["answered"], "duration_sec"].mean() / 60.0 if answered_calls else 0.0
    avg_pdd_ms = df["setup_time_ms"].mean()
    unique_callers = df["caller"].nunique(dropna=True)
    unique_callees = df["callee"].nunique(dropna=True)
    revenue = df["cost"].sum(skipna=True)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total calls", f"{total_calls:,}")
    c2.metric("Total minutes", f"{total_minutes:,.1f}")
    c3.metric("ASR", f"{asr*100:.1f}%")
    c4.metric("ACD (min)", f"{acd_min:.2f}")
    c5.metric("Avg PDD (ms)", f"{avg_pdd_ms:.0f}" if not np.isnan(avg_pdd_ms) else "—")
    c6.metric("Revenue", f"{revenue:,.2f}" if revenue and not np.isnan(revenue) else "—")

def time_charts(df):
    if df.empty:
        st.info("No data for selected filters.")
        return
    daily = df.groupby("date").agg(calls=("date", "count"), minutes=("duration_sec", lambda x: x.fillna(0).sum()/60)).reset_index()
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.line(daily, x="date", y="calls", title="Calls over time"), use_container_width=True)
    c2.plotly_chart(px.line(daily, x="date", y="minutes", title="Minutes over time"), use_container_width=True)

def heatmap(df):
    if df.empty:
        return
    weekdays = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    df = df.copy()
    df["weekday"] = pd.Categorical(df["weekday"], categories=weekdays, ordered=True)
    pivot = df.pivot_table(index="weekday", columns="hour", values="caller", aggfunc="count", fill_value=0)
    fig = px.imshow(pivot, aspect="auto", color_continuous_scale="Blues", title="Traffic heatmap (weekday vs hour)")
    st.plotly_chart(fig, use_container_width=True)

def top_entities(df):
    if df.empty:
        return
    n = 15
    top_callers = df.groupby("caller").size().sort_values(ascending=False).head(n).reset_index(name="calls")
    top_callees = df.groupby("callee").size().sort_values(ascending=False).head(n).reset_index(name="calls")
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.bar(top_callers, x="caller", y="calls", title="Top callers").update_layout(xaxis=dict(categoryorder='total descending')), use_container_width=True)
    c2.plotly_chart(px.bar(top_callees, x="callee", y="calls", title="Top callees").update_layout(xaxis=dict(categoryorder='total descending')), use_container_width=True)

def distributions(df):
    if df.empty:
        return
    c1, c2, c3 = st.columns(3)
    c1.plotly_chart(px.histogram(df, x="duration_sec", nbins=50, title="Duration distribution (sec)"), use_container_width=True)
    c2.plotly_chart(px.bar(df.groupby("direction").size().reset_index(name="calls"), x="direction", y="calls", title="Direction split"), use_container_width=True)
    if df["status"].notna().any():
        c3.plotly_chart(px.bar(df.groupby("status").size().reset_index(name="calls").sort_values("calls", ascending=False).head(15),
                               x="status", y="calls", title="Top statuses"), use_container_width=True)

def operator_quality(df):
    if df.empty or df["operator"].isna().all():
        return
    g = df.groupby("operator").agg(
        calls=("operator","count"),
        asr=("answered", "mean"),
        acd_min=("duration_sec", lambda x: x[df.loc[x.index, "answered"]].mean()/60 if (df.loc[x.index, "answered"]).any() else np.nan),
        minutes=("duration_sec", lambda x: x.fillna(0).sum()/60),
        pdd_ms=("setup_time_ms","mean")
    ).reset_index()
    fig = px.scatter(
        g, x="asr", y="acd_min", size="calls", color="minutes",
        hover_data=["operator","pdd_ms","calls","minutes"],
        labels={"asr":"ASR","acd_min":"ACD (min)"},
        title="Operator quality (ASR vs ACD, bubble = calls, color = minutes)"
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(g.sort_values("calls", ascending=False), use_container_width=True, height=300)

def downloads(df_all, df_filtered):
    with st.expander("Downloads"):
        csv_all = df_all.to_csv(index=False).encode("utf-8")
        csv_f = df_filtered.to_csv(index=False).encode("utf-8")
        st.download_button("Download full normalized CDR CSV", csv_all, file_name="cdr_normalized_all.csv", mime="text/csv")
        st.download_button("Download filtered CDR CSV", csv_f, file_name="cdr_filtered.csv", mime="text/csv")

# -------------------------------
# App
# -------------------------------
st.title("CDR Analysis & Auto-Dashboard")
st.caption("Upload your CDR file (CSV or Excel). Columns are auto-detected. Use the sidebar to filter.")

uploaded = st.file_uploader("Upload CDR file", type=["csv","xlsx","xls"])
demo = st.toggle("Use demo synthetic data", value=False)

if uploaded or demo:
    if demo:
        # Synthetic demo data (quick)
        np.random.seed(7)
        now = pd.Timestamp.now().normalize()
        rows = 3000
        starts = now - pd.to_timedelta(np.random.randint(0, 30*24*60, size=rows), unit="m")
        callers = np.random.choice([f"+92{np.random.randint(3000000000, 3999999999)}" for _ in range(500)], size=rows)
        callees = np.random.choice([f"+92{np.random.randint(3000000000, 3999999999)}" for _ in range(800)], size=rows)
        directions = np.random.choice(["inbound","outbound"], p=[0.45,0.55], size=rows)
        statuses = np.random.choice(["ANSWERED","NO_ANSWER","BUSY","FAILED"], p=[0.7,0.15,0.1,0.05], size=rows)
        durations = np.where(statuses=="ANSWERED", np.random.exponential(scale=120, size=rows), 0).astype(int)
        opers = np.random.choice(["Jazz","Telenor","Zong","Ufone"], size=rows)
        countries = np.random.choice(["Pakistan","UAE","Saudi Arabia","UK"], size=rows, p=[0.8,0.1,0.07,0.03])
        setup_ms = np.where(statuses=="ANSWERED", np.random.normal(2500, 700, size=rows), np.random.normal(1800, 600, size=rows)).clip(200, 10000)
        cost = (durations/60) * np.random.uniform(0.02, 0.08, size=rows)

        df_raw = pd.DataFrame({
            "start_time": starts,
            "duration_sec": durations,
            "caller": callers,
            "callee": callees,
            "direction": directions,
            "status": statuses,
            "operator": opers,
            "country": countries,
            "setup_time_ms": setup_ms.astype(int),
            "cost": cost
        })
    else:
        df_raw = load_data(uploaded)

    df = standardize_columns(df_raw)
    df_f = filter_data(df)

    kpi_cards(df_f)
    time_charts(df_f)
    heatmap(df_f)
    top_entities(df_f)
    operator_quality(df_f)
    distributions(df_f)
    downloads(df, df_f)

    with st.expander("Peek at normalized data"):
        st.dataframe(df_f.head(100), use_container_width=True)
else:
    st.info("Upload a CDR CSV/Excel file or enable demo data to get started.")
