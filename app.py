import pandas as pd
import streamlit as st
import altair as alt

# ---------- Streamlit page & style ---------- #
st.set_page_config(page_title="Julien's Workout Dashboard", layout="wide")
st.markdown("""
    <style>
      .stDataFrame {border:1px solid #eee;border-radius:10px;}
      .block-container {padding-top:1rem;}
      h3 {font-size: 1.4rem; font-weight: bold;}
    </style>
""", unsafe_allow_html=True)

st.title("🏋️ Julien's Workout Dashboard")
st.markdown(
    "Tracking Julien's sets, volume, and personal bests 🏅. "
    "View by day or by exercise. Volume trends include the selected day. "
    "Tracking my progress so Coach Azim has fewer reasons to be disappointed."
)

# ---------- Load data ---------- #
df = pd.read_csv("https://raw.githubusercontent.com/datojulien/workout-dashboard/main/WorkoutExport.csv")
df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df["Day"] = df["Date"].dt.date
# Exclude cardio-only rows
df = df[~df["Exercise"].str.contains("Stair Stepper|Cycling", case=False, na=False)]

# ---------- Derived metrics ---------- #
df["Actual Weight (kg)"] = df["Weight(kg)"].fillna(0) * df["multiplier"].fillna(1)
df["Volume (kg)"] = df["Actual Weight (kg)"] * df["Reps"].fillna(0)

# ---------- 1RM Estimate (Epley) ---------- #
def estimate_1rm(weight, reps):
    if reps and reps > 1:
        return weight * (1 + reps / 30)
    return weight

# apply only on weighted sets
df_weighted = df[df["Actual Weight (kg)"] > 0].copy()
df_weighted["1RM Estimate"] = df_weighted.apply(
    lambda r: estimate_1rm(r["Actual Weight (kg)"], r["Reps"]), axis=1
)

# ---------- PR Detection ---------- #
prs_weight = df[df["Actual Weight (kg)"] > 0].groupby("Exercise")["Actual Weight (kg)"].max().to_dict()
prs_reps = df[df["Actual Weight (kg)"] == 0].groupby("Exercise")["Reps"].max().to_dict()

def assign_pr(row):
    if row["Actual Weight (kg)"] == 0:
        return "🏅" if row["Reps"] == prs_reps.get(row["Exercise"], -1) else ""
    return "🏅" if row["Actual Weight (kg)"] == prs_weight.get(row["Exercise"], -1) else ""

df["PR"] = df.apply(assign_pr, axis=1)

# ---------- Classify workout type ---------- #
def classify_exercise(name) -> str:
    n = str(name).lower()
    lower_kw = ["squat","deadlift","lunge","leg","hamstring","calf",
                "hip thrust","thrust","glute","rdl","good morning"]
    push_kw  = ["bench","overhead press","shoulder press","incline",
                "dip","dips","push","tricep"]
    pull_kw  = ["row","pulldown","pull-up","curl","face pull","shrug","chin"]
    if any(k in n for k in lower_kw): return "Lower"
    if any(k in n for k in push_kw):  return "Push"
    if any(k in n for k in pull_kw):  return "Pull"
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

# ---------- Sidebar ---------- #
st.sidebar.title("Filters")
view_mode = st.sidebar.radio("📊 View Mode", ("By Date", "By Exercise"))
hide_light = st.sidebar.checkbox("💪 Azim View™ – Hide light sets (< 40 kg)")

if view_mode == "By Date":
    days = sorted(df["Day"].dropna().unique(), reverse=True)
    selected_day = st.sidebar.selectbox("📅 Select a date", days)
    df_view = df[df["Day"] == selected_day]
    if hide_light:
        df_view = df_view[df_view["Actual Weight (kg)"] >= 40]
    summary_title = (
        f"📊 Summary for {selected_day} | "
        f"{df_view['Workout Type'].value_counts().idxmax() if not df_view.empty else 'N/A'} Day"
    )
else:
    exercises = sorted(df["Exercise"].dropna().unique())
    selected_ex = st.sidebar.selectbox("💪 Select an exercise", exercises)
    df_view = df[df["Exercise"] == selected_ex]
    if hide_light:
        df_view = df_view[df_view["Actual Weight (kg)"] >= 40]
    summary_title = f"📊 Summary for {selected_ex}"

st.markdown(f"### {summary_title}", unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
c1.metric("Total Volume", f"{df_view['Volume (kg)'].sum():,.0f} kg")
c2.metric("Total Sets", len(df_view))
c3.metric("Heaviest Lift", f"{df_view['Actual Weight (kg)'].max():.1f} kg" if not df_view.empty else "—")

with st.expander("📆 Weekly Summary (last 4 weeks)", expanded=False):
    st.dataframe(weekly_summary.head(4), use_container_width=True)
    st.download_button(
        "📥 Download Weekly Summary CSV",
        weekly_summary.to_csv(index=False).encode('utf-8'),
        "weekly_summary.csv",
        "text/csv"
    )

if df_view.empty:
    st.info("No data for this selection.")
else:
    # ---------- 1RM Trend & Regression ---------- #
    irm = df_weighted.groupby('Day', as_index=False)['1RM Estimate'].max()
    base_irm = alt.Chart(irm).encode(
        x=alt.X('Day:T', axis=alt.Axis(format='%b %d', labelAngle=-45)),
        y=alt.Y('1RM Estimate:Q')
    )
    line_irm = base_irm.mark_line(point=True)
    reg_line = base_irm.transform_regression('Day', '1RM Estimate', method='linear').mark_line(strokeDash=[4,2])
    st.markdown("**📈 1RM Estimate Trend & Projection**")
    st.altair_chart((line_irm + reg_line).properties(height=250), use_container_width=True)

    # ---------- Acute:Chronic Workload Ratio ---------- #
    weekly_vol = weekly_summary.copy()
    acwr = weekly_vol['Total Volume'].iloc[0] / weekly_vol['Total Volume'].iloc[1:5].mean()
    st.markdown(f"**⚖️ ACWR (This week vs last 4 weeks avg):** {acwr:.2f}")

    pr_counts = df.groupby(pd.Grouper(key='Date', freq='W'))['PR'].apply(lambda x: x.eq('🏅').sum()).reset_index()
    pr_chart = alt.Chart(pr_counts).mark_bar().encode(
        x=alt.X('Date:T', title='Week'),
        y=alt.Y('PR:Q', title='PR Count')
    )
    st.markdown("**🏆 Weekly PR Counts**")
    st.altair_chart(pr_chart.properties
