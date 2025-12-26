import pandas as pd
import streamlit as st
import altair as alt
from datetime import timedelta
from supabase import create_client, Client

# ---------- Streamlit page config & style ---------- #
st.set_page_config(page_title="Julien's Workout Dashboard", layout="wide")
st.markdown("""<style>
    .stDataFrame {border:1px solid #eee;border-radius:10px;}
    .block-container {padding-top:1rem;}
    h3 {font-size: 1.4rem; font-weight: bold;}
</style>""", unsafe_allow_html=True)

st.title("🏋️ Julien's Workout Dashboard")

# ---------- Supabase Connection ---------- #
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["connections"]["supabase"]["url"]
        key = st.secrets["connections"]["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error("Missing Secrets! Ensure url and key are set in Streamlit Cloud.")
        st.stop()

supabase = init_connection()

# ---------- Load & preprocess data ---------- #
@st.cache_data(ttl=600)
def load_data():
    # FIX: Use 'desc' parameter instead of 'ascending'
    response = supabase.table("workouts") \
        .select("*") \
        .order("date", desc=True) \
        .limit(10000) \
        .execute()
    
    data = pd.DataFrame(response.data)
    
    if data.empty:
        return data

    # 1. Standardize column names and types
    data["Date"] = pd.to_datetime(data["date"], errors="coerce", utc=True).dt.tz_localize(None)
    data["Day"] = data["Date"].dt.date
    data["Exercise"] = data["exercise"]
    data["Reps"] = pd.to_numeric(data["reps"], errors='coerce').fillna(0)
    data["Weight_Single_KG"] = pd.to_numeric(data["weight_kg"], errors='coerce').fillna(0)
    data["Multiplier"] = pd.to_numeric(data["multiplier"], errors='coerce').fillna(1)
    
    # 2. Filtering
    data = data.dropna(subset=["Day"])
    data = data[~data["Exercise"].str.contains("Stair Stepper|Cycling", case=False, na=False)]

    # 3. Derived metrics
    data["Actual Weight (kg)"] = data["Weight_Single_KG"] * data["Multiplier"]
    data["Volume (kg)"] = data["Actual Weight (kg)"] * data["Reps"]
    
    return data

df = load_data()

# ---------- Sidebar Debugger & Filters ---------- #
st.sidebar.title("Filters & Debug")

if not df.empty:
    st.sidebar.write(f"📊 **Database Stats**")
    st.sidebar.write(f"Total Rows: `{len(df)}`")
    st.sidebar.write(f"Latest Entry: `{df['Day'].max()}`")
    st.sidebar.divider()

view_mode = st.sidebar.radio("View Mode", ("By Date", "By Exercise"))
hide_light = st.sidebar.checkbox("Azim View™ – Hide <40kg sets")
weeks = st.sidebar.slider("Show last N weeks for trends", 2, 52, 12)

if df.empty:
    st.warning("Connected to Supabase, but no data found.")
    st.stop()

# ---------- 1RM Estimate (Epley) ---------- #
def estimate_1rm(weight, reps):
    return weight * (1 + reps/30) if reps and reps > 1 else weight

df_weighted = df[df["Actual Weight (kg)"] > 0].copy()
df_weighted["1RM Estimate"] = df_weighted.apply(
    lambda r: estimate_1rm(r["Actual Weight (kg)"], r["Reps"]), axis=1
)

# ---------- PR Detection ---------- #
def assign_prs(data):
    prs_w = data[data["Actual Weight (kg)"] > 0].groupby("Exercise")["Actual Weight (kg)"].max().to_dict()
    prs_r = data[data["Actual Weight (kg)"] == 0].groupby("Exercise")["Reps"].max().to_dict()
    data["PR"] = data.apply(
        lambda r: (
            "🏅" if (
                (r["Actual Weight (kg)"] > 0 and r["Actual Weight (kg)"] == prs_w.get(r["Exercise"], 0)) or
                (r["Actual Weight (kg)"] == 0 and r["Reps"] == prs_r.get(r["Exercise"], -1))
            ) else ""
        ),
        axis=1
    )
    return data

df = assign_prs(df)

# ---------- Classify workout type ---------- #
def classify_exercise(name):
    n = str(name).lower()
    lowers = ["squat","deadlift","lunge","leg","hamstring","calf","hip thrust","thrust","glute","rdl","good morning"]
    pushes = ["bench","overhead press","shoulder press","incline","dip","push","tricep"]
    pulls = ["row","pulldown","pull-up","curl","face pull","shrug","chin"]
    if any(k in n for k in lowers): return "Lower"
    if any(k in n for k in pushes): return "Push"
    if any(k in n for k in pulls): return "Pull"
    return "Other"

df["Workout Type"] = df["Exercise"].apply(classify_exercise)

# ---------- Weekly summary ---------- #
df["Week"] = df["Date"].dt.isocalendar().week
weekly_summary = (
    df.groupby("Week", as_index=False)
      .agg({
          "Volume (kg)": "sum",
          "Actual Weight (kg)": "max",
          "Reps": "sum",
          "Exercise": "nunique"
      })
      .rename(columns={
          "Volume (kg)": "Total Volume",
          "Actual Weight (kg)": "Heaviest Lift",
          "Reps": "Total Reps",
          "Exercise": "Unique Exercises"
      })
      .sort_values("Week", ascending=False)
)

# ---------- Selection Logic ---------- #
if view_mode == "By Date":
    days = sorted(df["Day"].unique(), reverse=True)
    sel_day = st.sidebar.selectbox("Select a date", days)
    df_sel = df[df["Day"] == sel_day]
    if hide_light:
        df_sel = df_sel[df_sel["Actual Weight (kg)"] >= 40]
    
    workout_name = df_sel["note"].iloc[0] if not df_sel.empty and df_sel["note"].iloc[0] else "Workout"
    title = f"Summary for {sel_day} | {workout_name}"
else:
    exercises = sorted(df["Exercise"].unique())
    sel_ex = st.sidebar.selectbox("Select an exercise", exercises)
    df_sel = df[df["Exercise"] == sel_ex]
    if hide_light:
        df_sel = df_sel[df_sel["Actual Weight (kg)"] >= 40]
    title = f"Summary for {sel_ex}"

# ---------- Summary metrics ---------- #
st.header(title)
c1, c2, c3 = st.columns(3)
c1.metric("Total Volume", f"{df_sel['Volume (kg)'].sum():,.0f} kg")
c2.metric("Total Sets", len(df_sel))
c3.metric("Heaviest Lift", f"{df_sel['Actual Weight (kg)'].max():.1f} kg" if not df_sel.empty else "—")

# ---------- Trends ---------- #
cutoff = pd.Timestamp.today() - timedelta(weeks=weeks)
irm_data = df_weighted[df_weighted["Date"] >= cutoff]

if not irm_data.empty:
    irm_trend = irm_data.groupby("Date", as_index=False)["1RM Estimate"].max()
    base_irm = alt.Chart(irm_trend).encode(
        x=alt.X("Date:T", axis=alt.Axis(format="%b %d", labelAngle=-45)),
        y=alt.Y("1RM Estimate:Q", title="1RM Estimate (kg)")
    )
    st.altair_chart(
        (base_irm.mark_line(point=True, color="#ff4b4b") +
         base_irm.transform_regression("Date", "1RM Estimate").mark_line(strokeDash=[4, 2], color="gray"))
        .properties(height=250, title="Progress Trend (1RM Max)"),
        use_container_width=True
    )

# ---------- Detailed Table ---------- #
with st.expander("📋 Detailed sets/tables", expanded=True):
    display_df = df_sel.copy()
    display_df["Set #"] = range(1, len(display_df) + 1)
    
    cols_to_show = ["Set #", "Exercise", "Reps", "Weight_Single_KG", "Multiplier", "Actual Weight (kg)", "Volume (kg)", "PR"]
    if view_mode == "By Date":
        cols_to_show.remove("Exercise")
        for ex in df_sel["Exercise"].unique():
            st.subheader(ex)
            ex_df = display_df[display_df["Exercise"] == ex]
            st.dataframe(ex_df[cols_to_show], use_container_width=True, hide_index=True)
    else:
        st.dataframe(display_df[cols_to_show], use_container_width=True, hide_index=True)

# ---------- Raw Data Download ---------- #
st.divider()
st.download_button(
    "Download All Data (CSV)",
    df.to_csv(index=False).encode("utf-8"),
    "julien_workouts_supabase.csv",
    "text/csv"
)
