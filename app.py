import pandas as pd
import streamlit as st

# Set up the Streamlit page
st.set_page_config(page_title="🏋️ Julien's Workout Dashboard", layout="wide")

st.title("🏋️ Julien's Workout Dashboard")
st.markdown("Tracking Julien's workouts. View by day or by exercise. Personal records marked with 🏅")

# Load data from GitHub
csv_url = "https://raw.githubusercontent.com/datojulien/workout-dashboard/main/WorkoutExport.csv"
df = pd.read_csv(csv_url)
df['Date'] = pd.to_datetime(df['Date'])
df['Day'] = df['Date'].dt.date

# Filter out cardio
df = df[~df['Exercise'].str.contains("Stair Stepper", case=False, na=False)]

# Compute actual weight and volume
df['Actual Weight (kg)'] = df['Weight(kg)'] * df['multiplier']
df['Volume (kg)'] = df['Actual Weight (kg)'] * df['Reps']

# Identify PRs
exercise_prs = df.groupby('Exercise')['Actual Weight (kg)'].max().to_dict()
df['PR'] = df.apply(lambda row: "🏅" if row['Actual Weight (kg)'] == exercise_prs[row['Exercise']] else "", axis=1)

# Sidebar filters
st.sidebar.title("Filters")
view_mode = st.sidebar.radio("📊 View Mode", ["By Date", "By Exercise"])

if view_mode == "By Date":
    # Dropdown of workout days
    unique_days = sorted(df['Day'].unique(), reverse=True)
    selected_day = st.sidebar.selectbox("📅 Select a date", unique_days)
    
    df_day = df[df['Day'] == selected_day]
    st.header(f"Workout on {selected_day}")

    if df_day.empty:
        st.warning("No workouts on this date.")
    else:
        for exercise in df_day['Exercise'].unique():
            st.subheader(f"💪 {exercise}")
            df_ex = df_day[df_day['Exercise'] == exercise].reset_index(drop=True)
            df_ex['Set #'] = df_ex.groupby(['Day', 'Exercise']).cumcount() + 1

            df_display = df_ex[['Set #', 'Reps', 'Weight(kg)', 'multiplier',
                                'Actual Weight (kg)', 'Volume (kg)', 'PR']]
            st.dataframe(df_display, use_container_width=True)

elif view_mode == "By Exercise":
    # Dropdown of all unique exercises
    all_exercises = sorted(df['Exercise'].unique())
    selected_exercise = st.sidebar.selectbox("💪 Select an exercise", all_exercises)

    df_ex = df[df['Exercise'] == selected_exercise]
    st.header(f"All Sets for {selected_exercise}")

    if df_ex.empty:
        st.warning("No data available for this exercise.")
    else:
        for day in sorted(df_ex['Day'].unique(), reverse=True):
            st.subheader(f"📅 {day}")
            df_day = df_ex[df_ex['Day'] == day].reset_index(drop=True)
            df_day['Set #'] = df_day.groupby(['Day', 'Exercise']).cumcount() + 1

            df_display = df_day[['Set #', 'Reps', 'Weight(kg)', 'multiplier',
                                 'Actual Weight (kg)', 'Volume (kg)', 'PR']]
            st.dataframe(df_display, use_container_width=True)
