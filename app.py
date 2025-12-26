import pandas as pd
import streamlit as st
import altair as alt
from datetime import timedelta
from supabase import create_client, Client

# ---------- Page Config & Style ---------- #
st.set_page_config(page_title="Julien's Workout Dashboard", layout="wide")
st.markdown("""<style>
    .stDataFrame {border:1px solid #eee;border-radius:10px;}
    .block-container {padding-top:1rem;}
    h3 {font-size: 1.4rem; font-weight: bold;}
    .metric-card {background-color: #f0f2f6; padding: 15px; border-radius: 10px; border: 1px solid #ddd;}
</style>""", unsafe_allow_html=True)

st.title("🏋️ Julien's Workout Dashboard")
st.markdown("Tracking Julien's sets, volume, and personal bests 🏅.")

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

# ---------- Load & Preprocess Data ---------- #
@st.cache_data(ttl=600)
def load_data():
    response = supabase.table("workouts") \
        .select("*") \
        .order("date", desc=True) \
        .order("set_order", desc=False) \
        .limit(10000).execute()
    
    data = pd.DataFrame(response.data)
    if data.empty: return data

    # Core data mapping
    data["Date"] = pd.to_datetime(data["date"], errors="coerce", utc=True).dt.tz_localize(None)
    data["Day"] = data["Date"].dt.date
    data["Exercise"] = data["exercise"]
    data["Reps"] = pd.to_numeric(data["reps"], errors='coerce').fillna(0)
    data["Weight_Single_KG"] = pd.to_numeric(data["weight_kg"], errors='coerce').fillna(0)
    data["Multiplier"] = pd.to_numeric(data["multiplier"], errors='coerce').fillna(1)
    data["Set_Order"] = pd.to_numeric(data["set_order"], errors='coerce').fillna(1)
    
    # Filtering cardio
    data = data.dropna(subset=["Day"])
    data = data[~data["Exercise"].str.contains("Stair Stepper|Cycling", case=False, na=False)]

    # Derived metrics
    data["Actual Weight (kg)"] = data["Weight_Single_KG"] * data["Multiplier"]
    data["Volume (kg)"] = data["Actual Weight (kg)"] * data["Reps"]
    return data

df = load_data()

if df.empty:
    st.warning("No data found in Supabase.")
    st.stop()

# ---------- Original Function: 1RM Estimate (Epley) ---------- #
def estimate_1rm(weight, reps):
    return weight * (1 + reps/30) if reps and reps > 1 else weight

df["1RM_Estimate"] = df.apply(lambda r: estimate_1rm(r["Actual Weight (kg)"], r["Reps"]), axis=1)

# ---------- Original Function: PR Detection ---------- #
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

# ---------- Original Function: Workout Classification ---------- #
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

# ---------- Original Function: Weekly Summary ---------- #
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

# ---------- Intensity & Load Metrics ---------- #
all_time_maxes = df.groupby("Exercise")["1RM_Estimate"].max().to_dict()
df["Intensity %"] = df.apply(lambda r: (r["1RM_Estimate"] / all_time_maxes.get(r["Exercise"], 1)) * 100 if r["Actual Weight (kg)"] > 0 else 0, axis=1)

# ---------- Sidebar Filters ---------- #
st.sidebar.title("Filters & Settings")
view_mode = st.sidebar.radio("View Mode", ("By Date", "By Exercise"))
hide_light = st.sidebar.checkbox("Azim View™ – Hide <40kg sets")
weeks_count = st.sidebar.slider("Show last N weeks for trends", 2, 52, 8)

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

# ---------- Header Metrics ---------- #
st.header(title)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Volume", f"{df_sel['Volume (kg)'].sum():,.0f} kg")
c2.metric("Total Sets", len(df_sel))
c3.metric("Heaviest Lift", f"{df_sel['Actual Weight (kg)'].max():.1f} kg" if not df_sel.empty else "—")
c4.metric("Avg Intensity", f"{df_sel[df_sel['Actual Weight (kg)'] > 0]['Intensity %'].mean():.1f}%" if not df_sel.empty else "0%")

# ---------- Weekly Summary Expander ---------- #
with st.expander("Weekly summary (last 4 weeks)"):
    st.dataframe(weekly_summary.head(4), use_container_width=True)

# ---------- Trends Section ---------- #
st.subheader("Progress Trends")
cutoff = pd.Timestamp.today() - timedelta(weeks=weeks_count)

col_chart, col_pie = st.columns([2, 1])

with col_chart:
    # 1RM trend for the selection
    target_exercise = sel_ex if view_mode == "By Exercise" else (df_sel["Exercise"].iloc[0] if not df_sel.empty else None)
    if target_exercise:
        trend_data = df[(df["Exercise"] == target_exercise) & (df["Date"] >= cutoff)]
        if not trend_data.empty:
            chart_data = trend_data.groupby("Day")["1RM_Estimate"].max().reset_index()
            chart = alt.Chart(chart_data).mark_line(point=True, color="#ff4b4b").encode(
                x=alt.X("Day:T", title="Date"),
                y=alt.Y("1RM_Estimate:Q", title="Est. 1RM (kg)", scale=alt.Scale(zero=False))
            ).properties(height=300, title=f"1RM Progression: {target_exercise}")
            st.altair_chart(chart, use_container_width=True)

with col_pie:
    # Volume Category Split
    pie_data = df_sel.groupby("Workout Type")["Volume (kg)"].sum().reset_index()
    pie = alt.Chart(pie_data).mark_arc().encode(
        theta="Volume (kg):Q",
        color="Workout Type:N"
    ).properties(height=300, title="Volume Distribution")
    st.altair_chart(pie, use_container_width=True)

# ---------- Coach's Corner (ACWR) ---------- #
if len(weekly_summary) >= 2:
    acute = weekly_summary["Total Volume"].iloc[0]
    chronic = weekly_summary["Total Volume"].iloc[1:5].mean()
    if chronic > 0:
        ratio = acute / chronic
        st.info(f"⚖️ **ACWR (Acute:Chronic Workload Ratio):** {ratio:.2f} — " + 
                ("✅ Optimal" if 0.8 <= ratio <= 1.3 else "⚠️ Watch Recovery"))

# ---------- Detailed Tables ---------- #
with st.expander("📋 Detailed sets/tables", expanded=True):
    display_df = df_sel.copy()
    display_df["Intensity"] = display_df["Intensity %"].map("{:.1f}%".format)
    
    cols = ["Set_Order", "Reps", "Weight_Single_KG", "Multiplier", "Actual Weight (kg)", "Volume (kg)", "Intensity", "PR"]
    
    if view_mode == "By Date":
        for ex in df_sel["Exercise"].unique():
            st.write(f"**{ex}**")
            ex_df = display_df[display_df["Exercise"] == ex]
            st.dataframe(ex_df[cols], use_container_width=True, hide_index=True)
    else:
        st.dataframe(display_df[["Day"] + cols], use_container_width=True, hide_index=True)

# ---------- Full Export ---------- #
st.divider()
st.download_button("Download Full Database CSV", df.to_csv(index=False).encode("utf-8"), "julien_workouts.csv", "text/csv")
