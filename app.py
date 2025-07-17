import pandas as pd
import streamlit as st
import altair as alt

# ---------- Streamlit page & style ---------- #
st.set_page_config(page_title="Julien's Workout Dashboard", layout="wide")
st.markdown(
    """
    <style>
      .stDataFrame {border:1px solid #eee;border-radius:10px;}
      .block-container {padding-top:1rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🏋️ Julien's Workout Dashboard")
st.markdown(
    "Tracking Julien's sets, volume, and personal bests 🏅. "
    "View by day or by exercise. Volume trends include the selected day. "
    "Hopefully Coach Azim won't be ashamed by my performances."
)

# ---------- Load data ---------- #
CSV_URL = (
    "https://raw.githubusercontent.com/datojulien/workout-dashboard/main/WorkoutExport.csv"
)
df = pd.read_csv(CSV_URL)
df["Date"] = pd.to_datetime(df["Date"])
df["Day"] = df["Date"].dt.date

# Exclude cardio-only rows
df = df[~df["Exercise"].str.contains("Stair Stepper|Cycling", case=False, na=False)]

# ---------- Derived metrics ---------- #
df["Actual Weight (kg)"] = df["Weight(kg)"] * df["multiplier"]
df["Volume (kg)"] = df["Actual Weight (kg)"] * df["Reps"]

# Personal-record (PR) flag
prs = df.groupby("Exercise")["Actual Weight (kg)"].max().to_dict()
df["PR"] = df.apply(
    lambda r: "🏅" if r["Actual Weight (kg)"] == prs[r["Exercise"]] else "", axis=1
)

# ---------- Push / Pull / Lower classifier ---------- #
def classify_exercise(name: str) -> str:
    """Return Push / Pull / Lower / Other based on keywords."""
    n = name.lower()

    lower_kw = [
        "squat",
        "deadlift",
        "lunge",
        "leg",
        "hamstring",
        "calf",
        "hip thrust",
        "thrust",
        "glute",
        "rdl",
        "good morning",
    ]
    push_kw = [
        "bench",
        "overhead press",
        "shoulder press",
        "incline",
        "dip",
        "dips",
        "push",
        "tricep",
    ]
    pull_kw = ["row", "pulldown", "pull-up", "curl", "face pull", "shrug", "chin"]

    if any(k in n for k in lower_kw):
        return "Lower Body"
    if any(k in n for k in push_kw):
        return "Push"
    if any(k in n for k in pull_kw):
        return "Pull"
    return "Other"


df["Workout Type"] = df["Exercise"].apply(classify_exercise)

# ---------- Sidebar controls ---------- #
st.sidebar.title("Filters")
view_mode = st.sidebar.radio("📊 View Mode", ("By Date", "By Exercise"))
hide_light = st.sidebar.checkbox("💪 Azim View™ – Hide light sets (< 40 kg)")

if view_mode == "By Date":
    all_days = sorted(df["Day"].unique(), reverse=True)
    selected_day = st.sidebar.selectbox("📅 Select a date", all_days)

    df_view = df[df["Day"] == selected_day]
    if hide_light:
        df_view = df_view[df_view["Actual Weight (kg)"] >= 40]

    # --- Auto-detect workout day type --- #
    day_type = (
        df_view["Workout Type"].value_counts().idxmax()
        if not df_view.empty
        else "N/A"
    )
    summary_title = f"📊 Summary for {selected_day} &nbsp;|&nbsp; **{day_type} Day**"

else:  # By Exercise
    all_ex = sorted(df["Exercise"].unique())
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

# ---------- Display tables & mini charts ---------- #
if df_view.empty:
    st.info("No workout data for this selection.")
else:
    if view_mode == "By Date":
        for ex in df_view["Exercise"].unique():
            df_ex = df_view[df_view["Exercise"] == ex].copy()
            df_ex["Set #"] = df_ex.groupby(["Day", "Exercise"]).cumcount() + 1
            show_cols = [
                "Set #",
                "Reps",
                "Weight(kg)",
                "multiplier",
                "Actual Weight (kg)",
                "Volume (kg)",
                "PR",
            ]
            with st.expander(ex, expanded=True):
                st.markdown(f"### 💪 {ex}")
                st.dataframe(df_ex[show_cols], use_container_width=True)

                # ----- Last-5-sessions volume trend (incl. selected day) ----- #
                recent_days = (
                    df[df["Exercise"] == ex]["Day"]
                    .drop_duplicates()
                    .sort_values(ascending=False)
                )
                recent_days = recent_days[recent_days <= selected_day].head(5).sort_values()
                vh = (
                    df[(df["Exercise"] == ex) & (df["Day"].isin(recent_days))]
                    .groupby("Day", as_index=False)["Volume (kg)"]
                    .sum()
                )
                if not vh.empty and vh["Volume (kg)"].max() > 0:
                    st.markdown("**📈 Volume trend (last 5 sessions)**")
                    chart = (
                        alt.Chart(vh)
                        .mark_line(point=True)
                        .encode(
                            x="Day:T",
                            y=alt.Y("Volume (kg):Q", title="Volume (kg)"),
                        )
                        .properties(height=200)
                    )
                    st.altair_chart(chart, use_container_width=True)

    else:  # By Exercise
        for d in sorted(df_view["Day"].unique(), reverse=True):
            df_day = df_view[df_view["Day"] == d].copy()
            df_day["Set #"] = df_day.groupby(["Day", "Exercise"]).cumcount() + 1
            show_cols = [
                "Set #",
                "Reps",
                "Weight(kg)",
                "multiplier",
                "Actual Weight (kg)",
                "Volume (kg)",
                "PR",
            ]
            with st.expander(str(d), expanded=True):
                st.markdown(f"### 📅 {d}")
                st.dataframe(df_day[show_cols], use_container_width=True)

        # ----- Volume trend for selected exercise (latest 5 sessions) ----- #
        recent_days = (
            df[df["Exercise"] == selected_ex]["Day"]
            .drop_duplicates()
            .sort_values(ascending=False)
            .head(5)
            .sort_values()
        )
        vh = (
            df[(df["Exercise"] == selected_ex) & (df["Day"].isin(recent_days))]
            .groupby("Day", as_index=False)["Volume (kg)"]
            .sum()
        )
        if not vh.empty and vh["Volume (kg)"].max() > 0:
            st.markdown("**📈 Volume trend (last 5 sessions)**")
            chart = (
                alt.Chart(vh)
                .mark_line(point=True)
                .encode(
                    x="Day:T",
                    y=alt.Y("Volume (kg):Q", title="Volume (kg)"),
                )
                .properties(height=200)
            )
            st.altair_chart(chart, use_container_width=True)
