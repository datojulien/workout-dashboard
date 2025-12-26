import pandas as pd
import streamlit as st
import altair as alt
from datetime import timedelta
from supabase import create_client, Client

st.set_page_config(page_title="Julien's Workout Dashboard", layout="wide")
st.markdown("""<style>
    .stDataFrame {border:1px solid #eee;border-radius:10px;}
    .block-container {padding-top:1rem;}
</style>""", unsafe_allow_html=True)

st.title("🏋️ Julien's Workout Dashboard")

@st.cache_resource
def init_connection():
    url = st.secrets["connections"]["supabase"]["url"]
    key = st.secrets["connections"]["supabase"]["key"]
    return create_client(url, key)

supabase = init_connection()

@st.cache_data(ttl=600)
def load_data():
    # Order by date DESC (newest first) and set_order ASC (1, 2, 3...)
    response = supabase.table("workouts") \
        .select("*") \
        .order("date", desc=True) \
        .order("set_order", desc=False) \
        .limit(10000).execute()
    
    data = pd.DataFrame(response.data)
    if data.empty: return data

    data["Date"] = pd.to_datetime(data["date"], errors="coerce", utc=True).dt.tz_localize(None)
    data["Day"] = data["Date"].dt.date
    data["Exercise"] = data["exercise"]
    data["Reps"] = pd.to_numeric(data["reps"], errors='coerce').fillna(0)
    data["Weight_KG"] = pd.to_numeric(data["weight_kg"], errors='coerce').fillna(0)
    data["Multiplier"] = pd.to_numeric(data["multiplier"], errors='coerce').fillna(1)
    data["Set_Order"] = pd.to_numeric(data["set_order"], errors='coerce').fillna(1)
    
    data["Actual Weight (kg)"] = data["Weight_KG"] * data["Multiplier"]
    data["Volume (kg)"] = data["Actual Weight (kg)"] * data["Reps"]
    return data

df = load_data()

# Sidebar
st.sidebar.title("Filters & Debug")
if not df.empty:
    st.sidebar.write(f"Total Rows: `{len(df)}` | Latest: `{df['Day'].max()}`")

view_mode = st.sidebar.radio("View Mode", ("By Date", "By Exercise"))
hide_light = st.sidebar.checkbox("Azim View™ – Hide <40kg sets")
weeks = st.sidebar.slider("Weeks for trends", 2, 52, 12)

if df.empty:
    st.warning("No data found.")
    st.stop()

# 1RM & PRs
def estimate_1rm(w, r): return w * (1 + r/30) if r > 1 else w
df_weighted = df[df["Actual Weight (kg)"] > 0].copy()
df_weighted["1RM Estimate"] = df_weighted.apply(lambda r: estimate_1rm(r["Actual Weight (kg)"], r["Reps"]), axis=1)

prs_w = df[df["Actual Weight (kg)"] > 0].groupby("Exercise")["Actual Weight (kg)"].max().to_dict()
df["PR"] = df.apply(lambda r: "🏅" if (r["Actual Weight (kg)"] > 0 and r["Actual Weight (kg)"] == prs_w.get(r["Exercise"], 0)) else "", axis=1)

# Selection
if view_mode == "By Date":
    days = sorted(df["Day"].unique(), reverse=True)
    sel_day = st.sidebar.selectbox("Select date", days)
    df_sel = df[df["Day"] == sel_day]
    if hide_light: df_sel = df_sel[df_sel["Actual Weight (kg)"] >= 40]
    title = f"Summary for {sel_day}"
else:
    exercises = sorted(df["Exercise"].unique())
    sel_ex = st.sidebar.selectbox("Select exercise", exercises)
    df_sel = df[df["Exercise"] == sel_ex]
    title = f"Summary for {sel_ex}"

st.header(title)
c1, c2, c3 = st.columns(3)
c1.metric("Total Volume", f"{df_sel['Volume (kg)'].sum():,.0f} kg")
c2.metric("Total Sets", len(df_sel))
c3.metric("Heaviest Lift", f"{df_sel['Actual Weight (kg)'].max():.1f} kg")

# Trend Chart
cutoff = pd.Timestamp.today() - timedelta(weeks=weeks)
irm_trend = df_weighted[df_weighted["Date"] >= cutoff].groupby("Date")["1RM Estimate"].max().reset_index()
if not irm_trend.empty:
    chart = alt.Chart(irm_trend).mark_line(point=True, color="#ff4b4b").encode(
        x="Date:T", y=alt.Y("1RM Estimate:Q", title="1RM (kg)")
    ).properties(height=250)
    st.altair_chart(chart, use_container_width=True)

# Tables
with st.expander("📋 Detailed Table", expanded=True):
    cols = ["Set_Order", "Exercise", "Reps", "Weight_KG", "Multiplier", "Actual Weight (kg)", "Volume (kg)", "PR"]
    if view_mode == "By Date":
        for ex in df_sel["Exercise"].unique():
            st.subheader(ex)
            st.dataframe(df_sel[df_sel["Exercise"] == ex][cols[2:]], use_container_width=True, hide_index=True)
    else:
        st.dataframe(df_sel[cols], use_container_width=True, hide_index=True)
