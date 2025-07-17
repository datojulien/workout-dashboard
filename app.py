import pandas as pd
import streamlit as st

# Set up clean layout
st.set_page_config(page_title="Workout Dashboard", layout="wide")

# Basic style enhancements
st.markdown("""
    <style>
    .stDataFrame {border: 1px solid #eee; border-radius: 10px;}
    .block-container {padding-top: 1rem;}
    </style>
""", unsafe_allow_html=True)

st.title("🏋️ Workout Dashboard")

# Load CSV
csv_url = "https://raw.githubusercontent.com/datojulien/workout-dashboard/main/WorkoutExport.csv"
df = pd.read_csv(csv_url)
df['Date'] = pd.to_datetime(df['Date'])
df['Day'] = df['Date'].dt.date

# Filter out cardio
df = df[~df['Exercise'].str.contains("Stair Stepper", case=False, na=False)]

# Calculated columns
df['Actual Weight (kg)'] = df['Weight(kg)'] * df['multiplier']
df['Volume (kg)'] = df['Actual Weight (kg)'] * df['Reps']

# Mark PRs
exercise_prs = df.groupby('Exercise')['Actual Weight (kg)'].max().to_dict()
df['PR'] = df.apply(lambda row: "🏅" if row['Actual Weight (kg)'] == exercise_prs[row['Exercise']] else "", axis=1)

# Header metrics
total_volume = df['Volume (kg)'].sum()
total_sets = len(df)
top_lift = df['Actual Weight (kg)'].max()

st.markdown("### 📊 Summary")
cols = st.columns(3)
cols[0].metric("Total Volume", f"{total_volume:,.0f} kg")
cols[1].metric("Total Sets", f"{total_sets}")
cols[2].metric("Heaviest Lift", f"{top_lift:.1f} kg")

# View mode
st.sidebar.title("Filters")
view_mode = st.sidebar.radio("📊 View Mode", ["By Date", "By Exercise"])

if view_mode == "By Date":
    unique_days = sorted(df['Day'].unique(), reverse=True)
    selected_day = st.sidebar.selectbox("📅 Select a date", unique_days)
    df_day = df[df['Day'] == selected_day]

    st.markdown(f"### 🗓 Workout on {selected_day}")
    if df_day.empty:
        st.info("No workout data on this date.")
    else:
        for exercise in df_day['Exercise'].unique():
            df_ex = df_day[df_day['Exercise'] == exercise].reset_index(drop=True)
            df_ex['Set #'] = df_ex.groupby(['Day', 'Exercise']).cumcount() + 1
            df_display = df_ex[['Set #', 'Reps', 'Weight(kg)', 'multiplier',
                                'Actual Weight (kg)', 'Volume (kg)', 'PR']]
            with st.expander(f"💪 {exercise}", expanded=True):
                st.dataframe(df_display, use_container_width=True)

elif view_mode == "By Exercise":
    all_exercises = sorted(df['Exercise'].unique())
    selected_exercise = st.sidebar.selectbox("💪 Select an exercise", all_exercises)
    df_ex = df[df['Exercise'] == selected_exercise]

    st.markdown(f"### 🔎 All Sets for {selected_exercise}")
    if df_ex.empty:
        st.info("No data for this exercise.")
    else:
        for day in sorted(df_ex['Day'].unique(), reverse=True):
            df_day = df_ex[df_ex['Day'] == day].reset_index(drop=True)
            df_day['Set #'] = df_day.groupby(['Day', 'Exercise']).cumcount() + 1
            df_display = df_day[['Set #', 'Reps', 'Weight(kg)', 'multiplier',
                                 'Actual Weight (kg)', 'Volume (kg)', 'PR']]
            with st.expander(f"📅 {day}", expanded=False):
                st.dataframe(df_display, use_container_width=True)
