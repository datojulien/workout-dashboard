import pandas as pd
import streamlit as st

# Set page config
st.set_page_config(page_title="🏋️ Workout Dashboard", layout="wide")

st.title("🏋️ Workout Dashboard")
st.markdown("Track your workouts day by day. Filter by exercise and spot your personal bests 🏅.")

# Load data from GitHub
csv_url = "https://raw.githubusercontent.com/datojulien/workout-dashboard/main/WorkoutExport.csv"
df = pd.read_csv(csv_url)
df['Date'] = pd.to_datetime(df['Date'])
df['Day'] = df['Date'].dt.date

# Filter out cardio (e.g. Stair Stepper)
df = df[~df['Exercise'].str.contains("Stair Stepper", case=False, na=False)]

# Compute actual weight and volume
df['Actual Weight (kg)'] = df['Weight(kg)'] * df['multiplier']
df['Volume (kg)'] = df['Actual Weight (kg)'] * df['Reps']

# Identify PRs
exercise_prs = df.groupby('Exercise')['Actual Weight (kg)'].max().to_dict()
df['PR'] = df.apply(lambda row: "🏅" if row['Actual Weight (kg)'] == exercise_prs[row['Exercise']] else "", axis=1)

# Sidebar filters
st.sidebar.title("Filters")

# Date picker (dropdown)
unique_days = sorted(df['Day'].unique(), reverse=True)
selected_day = st.sidebar.selectbox("📅 Select a day", unique_days)

# Exercise filter (within selected day)
df_day = df[df['Day'] == selected_day]
exercises_today = sorted(df_day['Exercise'].unique())
exercise_filter = st.sidebar.selectbox("💪 Filter by exercise (optional)", ["All"] + exercises_today)

# Filter based on exercise
if exercise_filter != "All":
    df_day = df_day[df_day['Exercise'] == exercise_filter]

# Display data
st.header(f"Workout on {selected_day}")

if df_day.empty:
    st.warning("No data for this exercise on the selected day.")
else:
    for exercise in df_day['Exercise'].unique():
        st.subheader(f"💪 {exercise}")
        
        df_ex = df_day[df_day['Exercise'] == exercise].reset_index(drop=True)
        df_ex['Set #'] = df_ex.groupby(['Day', 'Exercise']).cumcount() + 1

        df_display = df_ex[['Set #', 'Reps', 'Weight(kg)', 'multiplier',
                            'Actual Weight (kg)', 'Volume (kg)', 'PR']]
        st.dataframe(df_display, use_container_width=True)
