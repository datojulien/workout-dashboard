import pandas as pd
import streamlit as st
import altair as alt
from datetime import timedelta
from st_supabase_connection import SupabaseConnection

# ---------- Streamlit page config & style ---------- #
st.set_page_config(page_title="Julien's Workout Dashboard", layout="wide")
st.markdown("""<style>
  .stDataFrame {border:1px solid #eee;border-radius:10px;}
  .block-container {padding-top:1rem;}
  h3 {font-size: 1.4rem; font-weight: bold;}
</style>""", unsafe_allow_html=True)

st.title("🏋️ Julien's Workout Dashboard")

# ---------- Load Data from Supabase ---------- #
# Initialize connection
conn = st.connection("supabase", type=SupabaseConnection)

@st.cache_data(ttl=600) # Cache for 10 minutes
def load_supabase_data():
    # Query the 'workouts' table
    response = conn.table("workouts").select("*").execute()
    return pd.DataFrame(response.data)

try:
    df_raw = load_supabase_data()
except Exception as e:
    st.error(f"Failed to connect to Supabase: {e}")
    st.stop()

# ---------- Preprocess data ---------- #
df = df_raw.copy()

# Map Supabase column names to the logic used in the app
# Supabase: date, exercise, reps, weight_kg, multiplier
df["Date"] = pd.to_datetime(df["date"], errors="coerce", utc=True).dt.tz_convert(None)
df["Day"] = df["Date"].dt.date
df["Exercise"] = df["exercise"]
df["Reps"] = df["reps"]
df["Weight(kg)"] = df["weight_kg"] # Keep this for table display compatibility

# Drop NaT days and cardio exercises
df = df.dropna(subset=["Day"])
df = df[~df["Exercise"].str.contains("Stair Stepper|Cycling", case=False, na=False)]

# Derived metrics
# Using the multiplier logic from your database
df["Actual Weight (kg)"] = df["weight_kg"].fillna(0) * df["multiplier"].fillna(1)
df["Volume (kg)"] = df["Actual Weight (kg)"] * df["Reps"].fillna(0)

# ---------- 1RM Estimate & PR Detection (Same as your original) ---------- #
def estimate_1rm(weight, reps):
    return weight * (1 + reps/30) if reps and reps > 1 else weight

df_weighted = df[df["Actual Weight (kg)"] > 0].copy()
df_weighted["1RM Estimate"] = df_weighted.apply(
    lambda r: estimate_1rm(r["Actual Weight (kg)"], r["Reps"]), axis=1
)

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

# ---------- Classify workout type (Same as your original) ---------- #
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

# ... [The rest of your UI logic (Sidebar, Metrics, Trends) stays exactly the same] ...
