import pandas as pd
import streamlit as st
import altair as alt
from datetime import timedelta

# ---------- Streamlit page config & style ---------- #
st.set_page_config(page_title="Julien's Workout Dashboard", layout="wide")
st.markdown("""<style>
  .stDataFrame {border:1px solid #eee;border-radius:10px;}
  .block-container {padding-top:1rem;}
  h3 {font-size: 1.4rem; font-weight: bold;}
</style>""", unsafe_allow_html=True)

st.title("🏋️ Julien's Workout Dashboard")
st.markdown(
    "Tracking Julien's sets, volume, and personal bests 🏅. "
    "View by day or by exercise. Collapsible tables and limited-week charts improve readability."
)

# ---------- Load & preprocess data ---------- #
df = pd.read_csv(
    "https://raw.githubusercontent.com/datojulien/workout-dashboard/main/WorkoutExport.csv"
)
df["Date"] = pd.to_datetime(df["Date"], errors="coerce", utc=True).dt.tz_convert(None)
df["Day"] = df["Date"].dt.date
# drop any NaT days
# Exclude cardio exercises
df = df.dropna(subset=["Day"])
df = df[~df["Exercise"].str.contains("Stair Stepper|Cycling", case=False, na=False)]

# Derived metrics
df["Actual Weight (kg)"] = df["Weight(kg)"].fillna(0) * df["multiplier"].fillna(1)
df["Volume (kg)"] = df["Actual Weight (kg)"] * df["Reps"].fillna(0)

# ---------- 1RM Estimate (Epley) ---------- #
def estimate_1rm(weight, reps):
    if reps and reps > 1:
        return weight * (1 + reps / 30)
    return weight

df_weighted = df[df["Actual Weight (kg)"] > 0].copy()
df_weighted["1RM Estimate"] = df_weighted.apply(
    lambda r: estimate_1rm(r["Actual Weight (kg)"], r["Reps"]), axis=1
)

# ---------- PR Detection ---------- #
def assign_prs(df):
    prs_w = df[df["Actual Weight (kg)"] > 0].groupby("Exercise")["Actual Weight (kg)"].max().to_dict()
    prs_r = df[df["Actual Weight (kg)"] == 0].groupby("Exercise")["Reps"].max().to_dict()
    df["PR"] = df.apply(lambda r: (
        "🏅" if (
            (r["Actual Weight (kg)"] > 0 and r["Actual Weight (kg)"] == prs_w.get(r["Exercise"], 0)) or
            (r["Actual Weight (kg)"] == 0 and r["Reps"] == prs_r.get(r["Exercise"], -1))
        ) else ""
    ), axis=1)
    return df

df = assign_prs(df)

# ---------- Classify workout type ---------- #
def classify_exercise(name):
    n = str(name).lower()
    lowers = ["squat","deadlift","lunge","leg","hamstring","calf","hip thrust","thrust","glute","rdl","good morning"]
    pushes = ["bench","overhead press","shoulder press","incline","dip","push","tricep"]
    pulls  = ["row","pulldown","pull-up","curl","face pull","shrug","chin"]
    if any(k in n for k in lowers): return "Lower"
    if any(k in n for k in pushes): return "Push"
    if any(k in n for k in pulls):  return "Pull"
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

# ---------- Sidebar filters ---------- #
st.sidebar.title("Filters & Settings")
view_mode = st.sidebar.radio("View Mode", ("By Date","By Exercise"))
hide_light = st.sidebar.checkbox("Azim View™ – Hide <40kg sets")
weeks = st.sidebar.slider("Show last N weeks for trends", min_value=2, max_value=52, value=8)

# ---------- Data selection ---------- #
if view_mode == "By Date":
    days = sorted(df["Day"].unique(), reverse=True)
    sel_day = st.sidebar.selectbox("Select a date", days)
    df_sel = df[df["Day"] == sel_day]
    if hide_light:
        df_sel = df_sel[df_sel["Actual Weight (kg)"] >= 40]
    title = f"Summary for {sel_day} | {df_sel['Workout Type'].mode().iat[0] if not df_sel.empty else 'N/A'} Day"
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

# ---------- Weekly summary expander ---------- #
with st.expander("Weekly summary (last 4 weeks)"):
    st.dataframe(weekly_summary.head(4), use_container_width=True)
    st.download_button(
        "Download weekly CSV",
        weekly_summary.to_csv(index=False).encode("utf-8"),
        "weekly_summary.csv",
        "text/csv"
    )

if df_sel.empty:
    st.info("No data for this selection.")
    st.stop()

# ---------- Trends expander ---------- #
with st.expander(f"📈 Trends (last {weeks} weeks)"):
    cutoff = pd.Timestamp.today() - timedelta(weeks=weeks)
    # 1RM trend
    irm = (
        df_weighted.groupby("Date", as_index=False)["1RM Estimate"].max()
        .query("Date >= @cutoff")
    )
    base_irm = alt.Chart(irm).encode(
        x=alt.X("Date:T", axis=alt.Axis(format="%b %d", labelAngle=-45)),
        y=alt.Y("1RM Estimate:Q")
    )
    st.altair_chart(
        (base_irm.mark_line(point=True) +
         base_irm.transform_regression("Date", "1RM Estimate", method="linear").mark_line(strokeDash=[4,2]))
        .properties(height=200),
        use_container_width=True
    )
    # PR counts
    pr = (
        df[df['Date'] >= cutoff]
          .groupby(pd.Grouper(key="Date", freq="W"))["PR"]
          .apply(lambda x: x.eq("🏅").sum())
          .reset_index(name="PR Count")
    )
    st.altair_chart(
        alt.Chart(pr)
        .mark_bar()
        .encode(x="Date:T", y="PR Count:Q")
        .properties(height=200),
        use_container_width=True
    )

# ---------- Breakdown charts expander ---------- #
with st.expander("💪 Breakdown charts"):
    vol_mg = df_sel.groupby("Workout Type")["Volume (kg)"].sum().reset_index()
    st.altair_chart(
        alt.Chart(vol_mg)
        .mark_bar()
        .encode(x="Workout Type:N", y="Volume (kg):Q")
        .properties(height=200),
        use_container_width=True
    )
    ex_dist = (
        df_sel["Exercise"].value_counts()
        .reset_index()
        .rename(columns={"index":"Exercise","Exercise":"Count"})
    )
    st.altair_chart(
        alt.Chart(ex_dist)
        .mark_bar()
        .encode(x="Count:Q", y=alt.Y("Exercise:N", sort="-x"))
        .properties(height=300),
        use_container_width=True
    )

# ---------- Detailed tables expander ---------- #
with st.expander("📋 Detailed sets/tables"):
    if view_mode == "By Date":
        for ex in df_sel["Exercise"].unique():
            with st.expander(f"{ex} sets"):
                df_ex = df_sel[df_sel["Exercise"] == ex].copy()
                df_ex["Set #"] = df_ex.groupby(["Day","Exercise"]).cumcount() + 1
                st.dataframe(
                    df_ex[["Set #","Reps","Weight(kg)","multiplier","Actual Weight (kg)","Volume (kg)","PR"]],
                    use_container_width=True
                )
    else:
        for d in sorted(df_sel["Day"].unique(), reverse=True):
            with st.expander(f"{d}"):
                df_day = df_sel[df_sel["Day"] == d].copy()
                df_day["Set #"] = df_day.groupby(["Day","Exercise"]).cumcount() + 1
                st.dataframe(
                    df_day[["Set #","Exercise","Reps","Weight(kg)","multiplier","Actual Weight (kg)","Volume (kg)","PR"]],
                    use_container_width=True
                )

# ---------- Download detailed CSV ---------- #
df_export = df_sel.copy()
df_export["Set #"] = df_export.groupby(["Day","Exercise"]).cumcount() + 1
st.download_button(
    "Download full CSV",
    df_export.to_csv(index=False).encode("utf-8"),
    f"export_{view_mode}.csv",
    "text/csv"
)
