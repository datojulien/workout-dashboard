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
CSV_URL = "https://raw.githubusercontent.com/datojulien/workout-dashboard/main/WorkoutExport.csv"
df = pd.read_csv(CSV_URL)
df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df["Day"] = df["Date"].dt.date

# Exclude cardio-only rows
df = df[~df["Exercise"].str.contains("Stair Stepper|Cycling", case=False, na=False)]

# ---------- Derived metrics ---------- #
df["Actual Weight (kg)"] = df["Weight(kg)"].fillna(0) * df["multiplier"].fillna(1)
df["Volume (kg)"] = df["Actual Weight (kg)"] * df["Reps"].fillna(0)

# ---------- PR Detection ---------- #
prs_weight = (
    df[df["Actual Weight (kg)"] > 0]
      .groupby("Exercise")["Actual Weight (kg)"]
      .max()
      .to_dict()
)
prs_reps = (
    df[df["Actual Weight (kg)"] == 0]
      .groupby("Exercise")["Reps"]
      .max()
      .to_dict()
)

def assign_pr(row):
    if row["Actual Weight (kg)"] == 0:
        return "🏅" if row["Reps"] == prs_reps.get(row["Exercise"], -1) else ""
    else:
        return "🏅" if row["Actual Weight (kg)"] == prs_weight.get(row["Exercise"], -1) else ""

df["PR"] = df.apply(assign_pr, axis=1)

# ---------- Push / Pull / Lower classifier ---------- #
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
view_mode  = st.sidebar.radio("📊 View Mode", ("By Date", "By Exercise"))
hide_light = st.sidebar.checkbox("💪 Azim View™ – Hide light sets (< 40 kg)")

if view_mode == "By Date":
    all_days = sorted(df["Day"].dropna().unique(), reverse=True)
    selected_day = st.sidebar.selectbox("📅 Select a date", all_days)
    df_view = df[df["Day"] == selected_day]
    if hide_light:
        df_view = df_view[df_view["Actual Weight (kg)"] >= 40]
    day_type = df_view["Workout Type"].value_counts().idxmax() if not df_view.empty else "N/A"
    summary_title = f"📊 Summary for {selected_day} | **{day_type} Day**"

else:  # By Exercise
    all_ex = sorted(df["Exercise"].dropna().unique())
    selected_ex = st.sidebar.selectbox("💪 Select an exercise", all_ex)
    df_view = df[df["Exercise"] == selected_ex]
    if hide_light:
        df_view = df_view[df_view["Actual Weight (kg)"] >= 40]
    summary_title = f"📊 Summary for {selected_ex}"

# ---------- Summary metrics ---------- #
total_vol = df_view["Volume (kg)"].sum()
total_sets = len(df_view)
heaviest = df_view["Actual Weight (kg)"].max()

st.markdown(f"### {summary_title}", unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
c1.metric("Total Volume", f"{total_vol:,.0f} kg")
c2.metric("Total Sets", total_sets)
c3.metric("Heaviest Lift", f"{heaviest:.1f} kg" if pd.notna(heaviest) else "—")

# ---------- Weekly summary expander ---------- #
with st.expander("📆 Weekly Summary (last 4 weeks)", expanded=False):
    st.dataframe(weekly_summary.head(4), use_container_width=True)
    csv_weekly = weekly_summary.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Weekly Summary CSV",
        data=csv_weekly,
        file_name="weekly_summary.csv",
        mime="text/csv"
    )

# ---------- Display & download ---------- #
if df_view.empty:
    st.info("No data for this selection.")
else:
    # prepare export
    df_export = df_view.copy()
    df_export["Set #"] = df_export.groupby(["Day","Exercise"]).cumcount() + 1
    export_cols = ["Day","Exercise","Set #","Reps","Weight(kg)",
                   "multiplier","Actual Weight (kg)","Volume (kg)","PR"]

    if view_mode == "By Date":
        for ex in df_view["Exercise"].dropna().unique():
            df_ex = df_view[df_view["Exercise"] == ex].copy()
            df_ex["Set #"] = df_ex.groupby(["Day","Exercise"]).cumcount() + 1
            show_cols = ["Set #","Reps","Weight(kg)","multiplier",
                         "Actual Weight (kg)","Volume (kg)","PR"]
            with st.expander(f"💪 {ex}", expanded=True):
                st.dataframe(df_ex[show_cols], use_container_width=True)

                # volume trend for last 5 sessions incl. selected day
                all_dates = (
                    df[df["Exercise"] == ex]["Day"]
                      .drop_duplicates()
                      .sort_values(ascending=False)
                )
                prev4 = all_dates[all_dates < selected_day].head(4)
                recent_days = sorted(pd.Index([selected_day]).append(prev4).unique())
                vh = (
                    df[(df["Exercise"] == ex)&(df["Day"].isin(recent_days))]
                      .groupby("Day", as_index=False)["Volume (kg)"]
                      .sum()
                )
                if not vh.empty and vh["Volume (kg)"].max() > 0:
                    st.markdown("**📈 Volume trend (last 5 sessions)**")
                    chart = (
                        alt.Chart(vh)
                        .mark_line(point=True)
                        .encode(
                            x=alt.X("Day:T", axis=alt.Axis(format="%b %d", tickCount=5, labelAngle=-45)),
                            y=alt.Y("Volume (kg):Q", title="Volume (kg)")
                        )
                        .properties(height=200)
                    )
                    st.altair_chart(chart, use_container_width=True)

        # download full workout CSV
        csv_full = df_export[export_cols].to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Full Workout CSV", csv_full, f"workout_{selected_day}.csv", "text/csv")

    else:  # By Exercise
        for d in sorted(df_view["Day"].dropna().unique(), reverse=True):
            df_day = df_view[df_view["Day"] == d].copy()
            df_day["Set #"] = df_day.groupby(["Day","Exercise"]).cumcount() + 1
            show_cols = ["Set #","Reps","Weight(kg)","multiplier",
                         "Actual Weight (kg)","Volume (kg)","PR"]
            with st.expander(f"📅 {d}", expanded=True):
                st.dataframe(df_day[show_cols], use_container_width=True)

        # volume trend for exercise
        recent_days = (
            df[df["Exercise"] == selected_ex]["Day"]
              .drop_duplicates()
              .sort_values(ascending=False)
              .head(5)
              .sort_values()
        )
        vh = (
            df[(df["Exercise"] == selected_ex)&(df["Day"].isin(recent_days))]
              .groupby("Day", as_index=False)["Volume (kg)"]
              .sum()
        )
        if not vh.empty and vh["Volume (kg)"].max() > 0:
            st.markdown("**📈 Volume trend (last 5 sessions)**")
            chart = (
                alt.Chart(vh)
                .mark_line(point=True)
                .encode(
                    x=alt.X("Day:T", axis=alt.Axis(format="%b %d", tickCount=5, labelAngle=-45)),
                    y=alt.Y("Volume (kg):Q", title="Volume (kg)")
                )
                .properties(height=200)
            )
            st.altair_chart(chart, use_container_width=True)

        # download full exercise CSV
        csv_full = df_export[export_cols].to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Full Exercise CSV", csv_full, f"{selected_ex.replace(' ','_')}_all.csv", "text/csv")
